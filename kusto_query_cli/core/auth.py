"""Azure CLI authentication mechanisms and subscription state."""
import json
import os
import platform
import re
import select
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

SUBSCRIPTIONS_CACHE_FILE = os.path.expanduser("~/.azure/mcp_subscriptions_cache.json")
AUTH_MODE_HOST_SHARED = "host_shared"
AUTH_MODE_CONTAINER_MANAGED = "container_managed"


def check_azure_cli_logged_in():
    """
    Checks if the user is logged in to the Azure CLI.

    Raises:
        SystemExit: If the Azure CLI is not installed or the user is not logged in.
    """
    # Detect the operating system
    os_name = platform.system().lower()

    if not is_azure_cli_installed(os_name):
        raise SystemExit("Error: Azure CLI is not installed. Please install it to proceed.")

    try:
        # Command to check Azure CLI version
        command = "az account show"

        # If the OS is Windows, modify the command to run it through cmd.exe
        if os_name == "windows":
            # Splitting the command into parts for Windows
            command = shlex.split(f'cmd.exe /c "{command}"')
        else:
            # Use shlex.split to ensure the command is properly split for non-Windows OSes
            command = shlex.split(command)

        # Execute 'az account show' to get the current account details
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    except subprocess.CalledProcessError:
        # Handle errors (e.g., not logged in)
        raise SystemExit(
            "Error: Not logged in to Azure CLI. Please log in using 'az login' before running this script.")


def is_azure_cli_installed(os_name: str | None = None):
    """
    Checks if the Azure CLI ('az') is installed and available in the system path.

    Parameters:
        os_name: Optional explicit OS name (e.g., 'windows', 'linux', 'darwin').
                 If not provided, it will be detected automatically.
    """
    try:
        # Detect OS if not provided
        if not os_name:
            os_name = platform.system().lower()

        # Command to check Azure CLI version
        command = "az --version"

        # If the OS is Windows, modify the command to run it through cmd.exe
        if os_name == "windows":
            # Splitting the command into parts for Windows
            command = shlex.split(f'cmd.exe /c "{command}"')
        else:
            # Use shlex.split to ensure the command is properly split for non-Windows OSes
            command = shlex.split(command)

        # Execute the command
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # If the command was successful, Azure CLI is installed
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking Azure CLI installation: {e}", file=sys.stderr)
        return False


def _emit_stderr_log(event: str, **fields) -> None:
    """Write a single structured log line to stderr without touching stdout."""
    try:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "component": "mcp-wrapper",
            "event": event,
        }
        payload.update(fields)
        sys.stderr.write(json.dumps(payload, separators=(",", ":")) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def get_timestamp():
    """Returns the current UTC timestamp in ISO-8601 format with 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_azure_auth_mode() -> str:
    mode = (os.environ.get("MCP_AZURE_AUTH_MODE", AUTH_MODE_CONTAINER_MANAGED) or "").strip().lower()
    if mode == AUTH_MODE_HOST_SHARED:
        return AUTH_MODE_HOST_SHARED
    return AUTH_MODE_CONTAINER_MANAGED


def is_host_shared_auth_mode() -> bool:
    return get_azure_auth_mode() == AUTH_MODE_HOST_SHARED


def get_auth_mode_message(auth_mode: str | None = None) -> str:
    mode = auth_mode or get_azure_auth_mode()
    if mode == AUTH_MODE_HOST_SHARED:
        return (
            "Authentication state is shared from the host. Manage Azure login and logout on the host "
            "with the Azure CLI, for example `az login`, `az account set --subscription <subscription-id>`, "
            "and `az logout`."
        )
    return "Authentication is managed inside the MCP container."


def run_command(cmd, timeout=None):
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.decode('utf-8', 'replace'), proc.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except FileNotFoundError as e:
        return 127, "", str(e)
    except Exception as e:
        return 1, "", str(e)


def is_authenticated():
    rc, out, _ = run_command(["az", "account", "show", "--only-show-errors"])
    if rc != 0:
        return False, {}
    try:
        data = json.loads(out or "{}")
        return True, data
    except Exception:
        return True, {}


def select_subscription(subscription_id: str) -> tuple[bool, str | None]:
    if not subscription_id:
        return True, None
    rc, out, err = run_command(["az", "account", "set", "--subscription", subscription_id, "--only-show-errors"])
    if rc == 0:
        return True, None
    return False, err or out or "Failed to set subscription"


def list_enabled_subscriptions() -> list[dict]:
    rc, out, _ = run_command(["az", "account", "list", "--query", "[?state=='Enabled']", "--only-show-errors"])
    if rc != 0:
        return []
    try:
        subs = json.loads(out or "[]")
        # Normalize keys of interest
        result = []
        for s in subs:
            result.append(
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "tenant_id": s.get("tenantId") or s.get("tenant_id"),
                    "is_default": bool(s.get("isDefault")),
                    "state": s.get("state"),
                }
            )
        return result
    except Exception:
        return []


def save_subscriptions_cache(subs: list[dict]) -> None:
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_CACHE_FILE), exist_ok=True)
        with open(SUBSCRIPTIONS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscriptions": subs, "cached_at": get_timestamp()}, f)
    except Exception:
        pass


def load_subscriptions_cache() -> list[dict] | None:
    try:
        with open(SUBSCRIPTIONS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            subs = data.get("subscriptions")
            if isinstance(subs, list):
                return subs
    except Exception:
        return None
    return None


def _start_login_background_monitor(subscription_id: str | None, timeout_seconds: int = 120) -> dict:
    """
    Start a background thread that waits for up to `timeout_seconds` attempting to
    finalize login and select the subscription. Intended for containerized runs.
    """
    result: dict = {"started": False}


    def _worker():
        start = time.time()
        # Poll is_authenticated and try to select subscription
        while time.time() - start < timeout_seconds:
            authed, _ = is_authenticated()
            if authed:
                elapsed_ms = int((time.time() - start) * 1000)
                _emit_stderr_log(
                    "azure_login_detected",
                    authenticated=True,
                    elapsed_ms=elapsed_ms,
                    subscription_id=subscription_id,
                )
                if subscription_id:
                    ok, err = select_subscription(subscription_id)
                    _emit_stderr_log(
                        "azure_subscription_selection",
                        authenticated=True,
                        elapsed_ms=elapsed_ms,
                        subscription_id=subscription_id,
                        success=ok,
                        error=err,
                    )
                    # Regardless of selection outcome, we consider the process finished
                break
            time.sleep(3)
        else:
            _emit_stderr_log(
                "azure_login_monitor_timeout",
                authenticated=False,
                timeout_seconds=timeout_seconds,
                subscription_id=subscription_id,
            )

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["started"] = True
    return result


def read_device_code(proc: subprocess.Popen, timeout_seconds: float = 4.0) -> tuple[str | None, str | None]:
    """
    Best-effort, strictly non-blocking attempt to capture the Azure CLI device-code and URL
    emitted shortly after starting `az login --use-device-code`.

    Uses fd-level non-blocking reads with select() and a hard deadline. Never blocks the caller
    longer than `timeout_seconds` (defaults to a small value). Returns (verification_url, device_code)
    or (None, None) if not yet available.
    """
    try:
        # Prepare raw fds (avoid buffered .read which may block) and set non-blocking if supported
        fds: list[int] = []
        fd_map: dict[int, str] = {}
        if proc.stderr is not None:
            try:
                fd = proc.stderr.fileno()
                try:
                    os.set_blocking(fd, False)  # type: ignore[attr-defined]
                except Exception:
                    pass
                fds.append(fd)
                fd_map[fd] = "err"
            except Exception:
                pass
        if proc.stdout is not None:
            try:
                fd = proc.stdout.fileno()
                try:
                    os.set_blocking(fd, False)  # type: ignore[attr-defined]
                except Exception:
                    pass
                fds.append(fd)
                fd_map[fd] = "out"
            except Exception:
                pass

        if not fds:
            return None, None

        deadline = time.time() + max(0.25, float(timeout_seconds))
        bufs: dict[str, bytearray] = {"out": bytearray(), "err": bytearray()}
        url: str | None = None
        code: str | None = None

        url_re = re.compile(r"https?://(?:\w+\.)*microsoft\.com/\S+", re.IGNORECASE)
        code_re = re.compile(r"\b([A-Z0-9]{4,}(?:-[A-Z0-9]{4,})*)\b")
        hint_re = re.compile(r"enter\s+the\s+code\s+([A-Z0-9-]{4,})|code\s*:\s*([A-Z0-9-]{4,})", re.IGNORECASE)

        while time.time() < deadline and fds:
            try:
                rlist, _, _ = select.select(fds, [], [], 0.15)
            except Exception:
                # Select may fail in some rare environments; break early rather than risk blocking
                break

            if not rlist:
                continue

            for fd in list(rlist):
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    continue
                except Exception:
                    # On error, stop watching this fd
                    try:
                        fds.remove(fd)
                    except Exception:
                        pass
                    continue

                if not chunk:
                    # EOF on this fd
                    try:
                        fds.remove(fd)
                    except Exception:
                        pass
                    continue

                bufs[fd_map.get(fd, "out")].extend(chunk)

            # Parse whatever we have so far
            try:
                s = (bufs["out"] + bufs["err"]).decode("utf-8", "replace")
            except Exception:
                s = ""

            if url is None:
                m_url = url_re.search(s)
                if m_url:
                    url = m_url.group(0)
            if code is None:
                m_hint = hint_re.search(s)
                if m_hint:
                    code = m_hint.group(1) or m_hint.group(2)
                if code is None:
                    m_code = code_re.search(s)
                    if m_code and len(m_code.group(1)) >= 6 and "http" not in m_code.group(1).lower():
                        code = m_code.group(1)

            if url or code:
                break

        return url, code
    except Exception:
        return None, None


def start_device_login():
    """Start Azure CLI device login without waiting for browser completion."""
    return subprocess.Popen(
        ["az", "login", "--use-device-code", "--only-show-errors"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
