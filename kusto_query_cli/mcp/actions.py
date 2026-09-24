"""Application actions shared by MCP transport and the one-shot adapter."""
import json
import os
import platform
import time
from kusto_query_cli.core import auth, proxy
from kusto_query_cli.core.query import execute_adx_query
from kusto_query_cli.core.serialization import _json_sanitize
from kusto_query_cli.resources import MANIFEST_FILE, load_version, load_protocol_version
from kusto_query_cli.mcp.envelopes import create_envelope


def handle_manifest(start_time: float):
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return create_envelope(
            action="MANIFEST",
            status="success",
            data=manifest,
            start_time=start_time,
            authenticated=auth.is_authenticated()[0],
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
    if not auth.is_azure_cli_installed(platform.system().lower()):
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

    authed, account = auth.is_authenticated()
    auth_mode = auth.get_azure_auth_mode()
    data = {
        "authenticated": authed,
        "azure_auth_mode": auth_mode,
        "message": auth.get_auth_mode_message(auth_mode),
        "proxy_config": proxy._load_proxy_config(),
    }
    if authed:
        data["account"] = account
    return create_envelope(
        action="AUTH_STATUS",
        status="success",
        data=data,
        start_time=start_time,
        authenticated=authed,
    )


def handle_login(start_time: float, subscription_id: str | None):
    if not auth.is_azure_cli_installed(platform.system().lower()):
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

    auth_mode = auth.get_azure_auth_mode()
    authed, account = auth.is_authenticated()
    if auth.is_host_shared_auth_mode():
        data = {
            "authenticated": authed,
            "login_required": not authed,
            "azure_auth_mode": auth_mode,
            "message": auth.get_auth_mode_message(auth_mode),
        }
        if authed:
            data["account"] = account
            data["subscriptions"] = auth.list_enabled_subscriptions()
        if subscription_id:
            data["requested_subscription_id"] = subscription_id
        return create_envelope(
            action="LOGIN",
            status="success",
            data=data,
            start_time=start_time,
            authenticated=authed,
        )

    if authed:
        # If already authenticated, optionally switch subscription
        if subscription_id:
            ok, err = auth.select_subscription(subscription_id)
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
        subs = auth.list_enabled_subscriptions()
        auth.save_subscriptions_cache(subs)
        return create_envelope(
            action="LOGIN",
            status="success",
            data={
                "authenticated": True,
                "account": account,
                "subscriptions": subs,
                "azure_auth_mode": auth_mode,
                "message": auth.get_auth_mode_message(auth_mode),
            },
            start_time=start_time,
            authenticated=True,
        )

    # Not authenticated: start device code login in a non-blocking way so MCP call does not hang
    # Using Popen to avoid waiting for the interactive device-code flow to complete.

    try:
        # Note: this process will keep running until the user completes authentication.
        # We do not wait for it here. Any device-code instructions will be printed by az to stderr.
        proc = auth.start_device_login()
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
    verification_url, device_code = auth.read_device_code(proc, timeout_seconds=4.0)

    # Start a background monitor to finalize login and select subscription if provided
    auth._start_login_background_monitor(subscription_id)

    # Provide well-known verification URL if CLI didn't emit it yet
    return create_envelope(
        action="LOGIN",
        status="success",
        data={
            "authenticated": False,
            "login_required": True,
            "azure_auth_mode": auth_mode,
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
    if not auth.is_azure_cli_installed(platform.system().lower()):
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

    auth_mode = auth.get_azure_auth_mode()
    if auth.is_host_shared_auth_mode():
        authed, _ = auth.is_authenticated()
        return create_envelope(
            action="LOGOUT",
            status="success",
            data={
                "logged_out": False,
                "azure_auth_mode": auth_mode,
                "message": auth.get_auth_mode_message(auth_mode),
            },
            start_time=start_time,
            authenticated=authed,
        )

    rc, _, err = auth.run_command(["az", "logout", "--only-show-errors"])
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
        if os.path.exists(auth.SUBSCRIPTIONS_CACHE_FILE):
            os.remove(auth.SUBSCRIPTIONS_CACHE_FILE)
    except Exception:
        pass

    return create_envelope(
        action="LOGOUT",
        status="success",
        data={
            "logged_out": True,
            "azure_auth_mode": auth_mode,
            "message": auth.get_auth_mode_message(auth_mode),
        },
        start_time=start_time,
        authenticated=False,
    )


def handle_list_subscriptions(start_time: float, subscription_id: str | None):
    if not auth.is_azure_cli_installed(platform.system().lower()):
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

    authed, account = auth.is_authenticated()
    if not authed:
        if auth.is_host_shared_auth_mode():
            return create_envelope(
                action="LIST_SUBSCRIPTIONS",
                status="success",
                data={
                    "subscriptions": auth.load_subscriptions_cache() or [],
                    "login_required": True,
                    "azure_auth_mode": auth.get_azure_auth_mode(),
                    "message": auth.get_auth_mode_message(),
                    "requested_subscription_id": subscription_id,
                },
                start_time=start_time,
                authenticated=False,
            )
        # Initiate login flow similar to handle_login, but also returns subscriptions when available
        env = handle_login(start_time, subscription_id)
        if env.get("status") == "success":
            # Attach best-effort cached subscriptions if available
            cached = auth.load_subscriptions_cache() or []
            env.setdefault("data", {})["subscriptions"] = cached
        return env

    # Already authenticated -> list subscriptions directly
    subs = auth.list_enabled_subscriptions()
    auth.save_subscriptions_cache(subs)
    return create_envelope(
        action="LIST_SUBSCRIPTIONS",
        status="success",
        data={
            "subscriptions": subs,
            "account": account,
            "azure_auth_mode": auth.get_azure_auth_mode(),
            "message": auth.get_auth_mode_message(),
        },
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
    if not auth.is_azure_cli_installed(platform.system().lower()):
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
    proxy_config = proxy._load_proxy_config()
    socks5_proxy = proxy_config["socks5_proxy"]
    socks5_dns = proxy_config["socks5_dns"]

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
            authenticated=auth.is_authenticated()[0],
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
            authenticated=auth.is_authenticated()[0],
        )


def handle_proxy_config(params: dict, start_time: float):
    clear_requested = proxy._to_bool(params.get("clear"), False)
    if clear_requested:
        proxy_config = proxy._clear_proxy_config()
    else:
        current = proxy._load_proxy_config()
        if "socks5_proxy" in params:
            current["socks5_proxy"] = proxy._normalize_proxy_value(params.get("socks5_proxy"))
        if "socks5_dns" in params:
            current["socks5_dns"] = proxy._to_bool(params.get("socks5_dns"), False)
        if not current["socks5_proxy"]:
            proxy_config = proxy._clear_proxy_config()
        else:
            proxy_config = proxy._save_proxy_config(current)

    return create_envelope(
        action="PROXY_CONFIG",
        status="success",
        data=proxy_config,
        start_time=start_time,
        authenticated=auth.is_authenticated()[0],
    )
