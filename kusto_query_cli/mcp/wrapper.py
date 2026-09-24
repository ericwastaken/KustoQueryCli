"""Read one action envelope from stdin and emit one response envelope."""
import json
import os
import platform
import sys
import time
from kusto_query_cli.core import auth
from kusto_query_cli.core.serialization import KustoEncoder
from kusto_query_cli.mcp import actions
from kusto_query_cli.mcp.envelopes import create_envelope

DEBUG_MODE = os.environ.get("MCP_DEBUG", "false").lower() == "true"


def print_json(obj):
    if DEBUG_MODE:
        print(json.dumps(obj, indent=2, cls=KustoEncoder))
    else:
        print(json.dumps(obj, separators=(",", ":"), cls=KustoEncoder))
    sys.stdout.flush()


def main():
    start_time = time.time()
    if not auth.is_azure_cli_installed(platform.system().lower()):
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

    is_object = isinstance(payload, dict)
    action = payload.get("action") if is_object else None
    params = payload.get("params", {}) if is_object else None
    if not is_object or not isinstance(params, dict) or (action is not None and not isinstance(action, str)):
        print_json(create_envelope(
            action=action if isinstance(action, str) else "UNKNOWN",
            status="error",
            error={
                "type": "validation",
                "code": "INVALID_REQUEST",
                "message": "Request and params must be JSON objects; action must be a string.",
                "retryable": False,
                "severity": "low",
            },
            start_time=start_time,
            authenticated=False,
        ))
        return

    try:
        if action == "MANIFEST":
            env = actions.handle_manifest(start_time)
        elif action == "AUTH_STATUS":
            env = actions.handle_auth_status(start_time)
        elif action == "LOGIN":
            env = actions.handle_login(start_time, params.get("subscription_id"))
        elif action == "LOGOUT":
            env = actions.handle_logout(start_time)
        elif action == "LIST_SUBSCRIPTIONS":
            env = actions.handle_list_subscriptions(start_time, params.get("subscription_id"))
        elif action == "QUERY":
            env = actions.handle_query(
                {
                    "query": params.get("query"),
                    "database": params.get("database"),
                    "cluster_url": params.get("cluster_url"),
                },
                start_time,
            )
        elif action == "PROXY_CONFIG":
            proxy_params = {}
            if "socks5_proxy" in params:
                proxy_params["socks5_proxy"] = params.get("socks5_proxy")
            if "socks5_dns" in params:
                proxy_params["socks5_dns"] = params.get("socks5_dns")
            if "clear" in params:
                proxy_params["clear"] = params.get("clear")
            env = actions.handle_proxy_config(proxy_params, start_time)
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
