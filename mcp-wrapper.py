import sys
import json
import time
import subprocess
import os
import re
import platform
import shlex
import threading
import tempfile
import uuid
from datetime import datetime, timezone
from lib.KustoHandler import execute_adx_query
from lib.AzureCliHelper import is_azure_cli_installed
import select

"""
mcp-wrapper.py: A Model Context Protocol (MCP) wrapper for Azure Data Explorer (ADX).

This script allows AI models to interact with ADX by providing a structured JSON interface
for common operations such as authentication, listing subscriptions, and executing queries.
It is designed to run either directly or inside a Docker container.

Input (via stdin):
    A JSON object with at least an "action" field and an optional "params" object.
    Example: {"action": "QUERY", "params": {"query": "...", "database": "...", "cluster_url": "..."}}

Actions:
    - LOGIN: Initiates or verifies Azure CLI authentication.
    - LOGOUT: Clears the current Azure CLI session and local caches.
    - AUTH_STATUS: Checks the current authentication status and returns account details.
    - LIST_SUBSCRIPTIONS: Returns a list of available Azure subscriptions (cached after login).
    - QUERY: Executes a Kusto query and returns the results as a list of objects.

Parameters (Environment Variables):
    - MCP_DEBUG: Set to "true" to enable pretty-printing and detailed error messages.

Usage Notes:
    - The script uses the Azure CLI ('az') for authentication.
    - If authentication is required, it initiates a device code login flow.
    - In Docker, a background monitor process handles the 'az login' interactive steps.
"""

# Global settings
VERSION_FILE = os.path.join(os.path.dirname(__file__), "mcp-wrapper-version")
PROTOCOL_VERSION_FILE = os.path.join(os.path.dirname(__file__), "mcp-protocol-version")
MANIFEST_FILE = os.path.join(os.path.dirname(__file__), "mcp-manifest.json")

def load_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"

def load_protocol_version():
    try:
        with open(PROTOCOL_VERSION_FILE, "r") as f:
            return f.read().strip()
    except:
        return "1.0"

WRAPPER_VERSION = load_version()
PROTOCOL_VERSION = load_protocol_version()
DEBUG_MODE = os.environ.get("MCP_DEBUG", "false").lower() == "true"
SUBSCRIPTIONS_CACHE_FILE = os.path.expanduser("~/.azure/mcp_subscriptions_cache.json")

class KustoEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle types not supported by default, 
    such as datetime objects and numpy types from pandas DataFrames.
    """
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        # Handle pandas/numpy types if needed
        try:
            import numpy as np
            if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)

def _json_sanitize(value):
    """Best-effort conversion to JSON-serializable structures.

    Mirrors the approach used by the MCP STDIO server: convert pandas
    DataFrame/Series when available, handle numpy scalars/arrays, and
    datetime-like objects with isoformat. Falls back to string when needed.
    """
    # Fast path for primitives
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # Datetime-like (duck-typing via isoformat)
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass

    # pandas integration (optional)
    try:
        import pandas as pd  # type: ignore
    except Exception:
        pd = None  # type: ignore

    if pd is not None:
        try:
            if isinstance(value, pd.DataFrame):
                try:
                    # Convert to list of records and sanitize nested values
                    return [
                        {str(k): _json_sanitize(v) for k, v in row.items()}
                        for row in value.to_dict(orient="records")
                    ]
                except Exception:
                    # Fallback to JSON string if conversion fails
                    return json.loads(value.to_json(orient="records"))
            if isinstance(value, pd.Series):
                try:
                    return [_json_sanitize(v) for v in value.tolist()]
                except Exception:
                    try:
                        return {str(k): _json_sanitize(v) for k, v in value.to_dict().items()}
                    except Exception:
                        return str(value)
        except Exception:
            pass

    # NumPy scalars/arrays
    try:
        import numpy as np  # type: ignore
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.ndarray,)):
            return [_json_sanitize(v) for v in value.tolist()]
    except Exception:
        pass

    # Bytes/bytearray → utf-8 or base64
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            import base64
            return base64.b64encode(bytes(value)).decode("ascii")

    # Sets/Tuples → lists
    if isinstance(value, (set, tuple)):
        return [_json_sanitize(v) for v in value]

    # Mappings → dict
    try:
        if isinstance(value, dict):
            return {str(k): _json_sanitize(v) for k, v in value.items()}
    except Exception:
        pass

    # Iterables (last resort) → list
    try:
        from collections.abc import Iterable
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            return [_json_sanitize(v) for v in list(value)]
    except Exception:
        pass

    # Fallback to string
    try:
        return str(value)
    except Exception:
        return None

def get_timestamp():
    """Returns the current UTC timestamp in ISO-8601 format with 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def create_envelope(action, status="success", data=None, error=None, start_time=None, authenticated=False, metadata_extra=None, request_id=None):
    """
    Wraps the response in a standard JSON envelope with metadata.
    
    Args:
        action (str): The name of the action being responded to.
        status (str): "success" or "error".
        data (dict, optional): The payload for successful responses.
        error (dict, optional): Error details (type, code, message, details).
        start_time (float, optional): Start time of the execution for performance tracking.
        authenticated (bool): Current authentication status.
        metadata_extra (dict, optional): Additional metadata to include.
        request_id (str, optional): Unique ID of the request being responded to.
        
    Returns:
        dict: The complete response envelope.
    """
    execution_time_ms = int((time.time() - start_time) * 1000) if start_time else 0
    
    metadata = {
        "timestamp": get_timestamp(),
        "execution_time_ms": execution_time_ms,
        "authenticated": authenticated,
        "wrapper_version": WRAPPER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
    }
    # Always include a request_id to satisfy the response schema; generate one if not provided
    if request_id is None:
        try:
            request_id = str(uuid.uuid4())
        except Exception:
            request_id = "00000000-0000-0000-0000-000000000000"
    metadata["request_id"] = request_id
    if metadata_extra:
        try:
            metadata.update(metadata_extra)
        except Exception:
            pass

    response = {
        "status": status,
        "action": action,
        "data": data if data is not None else {},
        "error": error if error is not None else {},
        "metadata": metadata,
    }
    return response

def print_json(obj):
    if DEBUG_MODE:
        print(json.dumps(obj, indent=2, cls=KustoEncoder))
    else:
        print(json.dumps(obj, separators=(",", ":"), cls=KustoEncoder))
    sys.stdout.flush()

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

def handle_manifest(start_time: float):
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return create_envelope(
            action="MANIFEST",
            status="success",
            data=manifest,
            start_time=start_time,
            authenticated=is_authenticated()[0],
        )
    except Exception as e:
        return create_envelope(
            action="MANIFEST",
            status="error",
            error={
                "type": "internal",
                "code": "WRAPPER_EXCEPTION",
                "message": f"Failed to load manifest: {e}",
                "retryable": False,
                "severity": "low",
            },
            start_time=start_time,
            authenticated=False,
        )

def handle_auth_status(start_time: float):
    if not is_azure_cli_installed(platform.system().lower()):
        return create_envelope(
            action="AUTH_STATUS",
            status="error",
            error={
                "type": "internal",
                "code": "AZ_CLI_NOT_FOUND",
                "message": "Azure CLI (az) is not installed.",
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )

    authed, account = is_authenticated()
    data = {"authenticated": authed}
    if authed:
        data["account"] = account
    return create_envelope(
        action="AUTH_STATUS",
        status="success",
        data=data,
        start_time=start_time,
        authenticated=authed,
    )

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
                if subscription_id:
                    ok, _ = select_subscription(subscription_id)
                    # Regardless of selection outcome, we consider the process finished
                break
            time.sleep(3)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["started"] = True
    return result

def handle_login(start_time: float, subscription_id: str | None):
    if not is_azure_cli_installed(platform.system().lower()):
        return create_envelope(
            action="LOGIN",
            status="error",
            error={
                "type": "internal",
                "code": "AZ_CLI_NOT_FOUND",
                "message": "Azure CLI (az) is not installed.",
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )

    authed, account = is_authenticated()
    if authed:
        # If already authenticated, optionally switch subscription
        if subscription_id:
            ok, err = select_subscription(subscription_id)
            if not ok:
                return create_envelope(
                    action="LOGIN",
                    status="error",
                    error={
                        "type": "authentication",
                        "code": "AZ_LOGIN_FAILED",
                        "message": err or "Failed to select subscription",
                        "retryable": True,
                        "severity": "low",
                    },
                    start_time=start_time,
                    authenticated=True,
                )
        subs = list_enabled_subscriptions()
        save_subscriptions_cache(subs)
        return create_envelope(
            action="LOGIN",
            status="success",
            data={"authenticated": True, "account": account, "subscriptions": subs},
            start_time=start_time,
            authenticated=True,
        )

    # Not authenticated: start device code login in a non-blocking way so MCP call does not hang
    # Using Popen to avoid waiting for the interactive device-code flow to complete.

    def _read_device_code_from_proc(proc: subprocess.Popen, timeout_seconds: float = 4.0) -> tuple[str | None, str | None]:
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
    try:
        # Note: this process will keep running until the user completes authentication.
        # We do not wait for it here. Any device-code instructions will be printed by az to stderr.
        proc = subprocess.Popen(
            ["az", "login", "--use-device-code", "--only-show-errors"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _ = proc  # keep reference for clarity; process runs independently
    except FileNotFoundError as e:
        return create_envelope(
            action="LOGIN",
            status="error",
            error={
                "type": "authentication",
                "code": "AZ_LOGIN_FAILED",
                "message": str(e),
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )
    except Exception as e:
        return create_envelope(
            action="LOGIN",
            status="error",
            error={
                "type": "authentication",
                "code": "AZ_LOGIN_FAILED",
                "message": f"Failed to start device code login: {e}",
                "retryable": True,
                "severity": "medium",
            },
            start_time=start_time,
            authenticated=False,
        )

    # Try to capture device code quickly (best-effort, bounded by small timeout)
    verification_url, device_code = _read_device_code_from_proc(proc, timeout_seconds=4.0)

    # Start a background monitor to finalize login and select subscription if provided
    _start_login_background_monitor(subscription_id)

    # Provide well-known verification URL if CLI didn't emit it yet
    return create_envelope(
        action="LOGIN",
        status="success",
        data={
            "authenticated": False,
            "verification_url": verification_url or "https://microsoft.com/devicelogin",
            "device_code": device_code,
            "message": (
                "A device-code login has been initiated. Open the verification URL and enter the code shown here. "
                "Authentication will be detected automatically."
            ),
        },
        start_time=start_time,
        authenticated=False,
    )

def handle_logout(start_time: float):
    if not is_azure_cli_installed(platform.system().lower()):
        return create_envelope(
            action="LOGOUT",
            status="error",
            error={
                "type": "internal",
                "code": "AZ_CLI_NOT_FOUND",
                "message": "Azure CLI (az) is not installed.",
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )

    rc, _, err = run_command(["az", "logout", "--only-show-errors"])
    if rc != 0:
        return create_envelope(
            action="LOGOUT",
            status="error",
            error={
                "type": "authentication",
                "code": "AZ_LOGOUT_FAILED",
                "message": err or "Logout failed",
                "retryable": True,
                "severity": "low",
            },
            start_time=start_time,
            authenticated=False,
        )

    # Clear cache
    try:
        if os.path.exists(SUBSCRIPTIONS_CACHE_FILE):
            os.remove(SUBSCRIPTIONS_CACHE_FILE)
    except Exception:
        pass

    return create_envelope(
        action="LOGOUT",
        status="success",
        data={"logged_out": True},
        start_time=start_time,
        authenticated=False,
    )

def handle_list_subscriptions(start_time: float, subscription_id: str | None):
    if not is_azure_cli_installed(platform.system().lower()):
        return create_envelope(
            action="LIST_SUBSCRIPTIONS",
            status="error",
            error={
                "type": "internal",
                "code": "AZ_CLI_NOT_FOUND",
                "message": "Azure CLI (az) is not installed.",
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )

    authed, account = is_authenticated()
    if not authed:
        # Initiate login flow similar to handle_login, but also returns subscriptions when available
        env = handle_login(start_time, subscription_id)
        if env.get("status") == "success":
            # Attach best-effort cached subscriptions if available
            cached = load_subscriptions_cache() or []
            env.setdefault("data", {})["subscriptions"] = cached
        return env

    # Already authenticated -> list subscriptions directly
    subs = list_enabled_subscriptions()
    save_subscriptions_cache(subs)
    return create_envelope(
        action="LIST_SUBSCRIPTIONS",
        status="success",
        data={"subscriptions": subs, "account": account},
        start_time=start_time,
        authenticated=True,
    )

def _validate_query_params(params: dict) -> tuple[bool, str | None]:
    required = ["query", "database", "cluster_url"]
    for p in required:
        if not params.get(p):
            return False, f"Missing required parameter: {p}"
    return True, None

def handle_query(params: dict, start_time: float):
    if not is_azure_cli_installed(platform.system().lower()):
        return create_envelope(
            action="QUERY",
            status="error",
            error={
                "type": "internal",
                "code": "AZ_CLI_NOT_FOUND",
                "message": "Azure CLI (az) is not installed.",
                "retryable": False,
                "severity": "high",
            },
            start_time=start_time,
            authenticated=False,
        )

    ok, err = _validate_query_params(params or {})
    if not ok:
        return create_envelope(
            action="QUERY",
            status="error",
            error={
                "type": "validation",
                "code": "MISSING_PARAMS",
                "message": err or "Missing required parameters",
                "retryable": False,
                "severity": "low",
            },
            start_time=start_time,
            authenticated=False,
        )

    cluster_url = params.get("cluster_url")
    database = params.get("database")
    query = params.get("query")
    socks5_proxy = params.get("socks5_proxy")
    socks5_dns = bool(params.get("socks5_dns", False))

    try:
        rows = execute_adx_query(
            cluster_url=cluster_url,
            database=database,
            query=query,
            socks5_proxy=socks5_proxy,
            socks5_dns=socks5_dns,
        )
        # Sanitize result to JSON-serializable structure (align with MCP STDIO server)
        sanitized = _json_sanitize(rows)
        # Include row_count to satisfy QUERY.response.schema.json
        row_count = 0
        try:
            # Prefer original DataFrame length when available
            try:
                import pandas as pd  # type: ignore
            except Exception:
                pd = None  # type: ignore
            if pd is not None and isinstance(rows, pd.DataFrame):
                row_count = len(rows)
            elif hasattr(sanitized, "__len__") and not isinstance(sanitized, (str, bytes, bytearray)):
                row_count = len(sanitized)
        except Exception:
            row_count = 0
        return create_envelope(
            action="QUERY",
            status="success",
            data={"result": sanitized, "row_count": row_count},
            start_time=start_time,
            authenticated=is_authenticated()[0],
        )
    except Exception as e:
        return create_envelope(
            action="QUERY",
            status="error",
            error={
                "type": "execution",
                "code": "KUSTO_QUERY_FAILED",
                "message": str(e),
                "retryable": False,
                "severity": "medium",
            },
            start_time=start_time,
            authenticated=is_authenticated()[0],
        )

def main():
    start_time = time.time()
    if not is_azure_cli_installed(platform.system().lower()):
        print_json(
            create_envelope(
                action="INIT",
                status="error",
                error={
                    "type": "internal",
                    "code": "AZ_CLI_NOT_FOUND",
                    "message": "Azure CLI (az) is not installed.",
                    "retryable": False,
                    "severity": "high",
                },
                start_time=start_time,
                authenticated=False,
            )
        )
        return

    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        print_json(
            create_envelope(
                action="UNKNOWN",
                status="error",
                error={
                    "type": "validation",
                    "code": "JSON_PARSE_ERROR",
                    "message": f"Invalid JSON: {e}",
                    "retryable": False,
                    "severity": "low",
                },
                start_time=start_time,
                authenticated=False,
            )
        )
        return

    action = (payload or {}).get("action")
    params = (payload or {}).get("params") or {}

    try:
        if action == "MANIFEST":
            env = handle_manifest(start_time)
        elif action == "AUTH_STATUS":
            env = handle_auth_status(start_time)
        elif action == "LOGIN":
            env = handle_login(start_time, params.get("subscription_id"))
        elif action == "LOGOUT":
            env = handle_logout(start_time)
        elif action == "LIST_SUBSCRIPTIONS":
            env = handle_list_subscriptions(start_time, params.get("subscription_id"))
        elif action == "QUERY":
            env = handle_query(
                {
                    "query": params.get("query"),
                    "database": params.get("database"),
                    "cluster_url": params.get("cluster_url"),
                    "socks5_proxy": params.get("socks5_proxy"),
                    "socks5_dns": bool(params.get("socks5_dns", False)),
                },
                start_time,
            )
        else:
            env = create_envelope(
                action=action or "UNKNOWN",
                status="error",
                error={
                    "type": "validation",
                    "code": "UNKNOWN_ACTION",
                    "message": f"Unknown action: {action}",
                    "retryable": False,
                    "severity": "low",
                },
                start_time=start_time,
                authenticated=False,
            )
    except Exception as e:
        env = create_envelope(
            action=action or "UNKNOWN",
            status="error",
            error={
                "type": "internal",
                "code": "WRAPPER_EXCEPTION",
                "message": str(e),
                "retryable": False,
                "severity": "medium",
            },
            start_time=start_time,
            authenticated=False,
        )

    print_json(env)

if __name__ == "__main__":
    main()
