import asyncio
import os
import sys
import time
from typing import Any
from datetime import datetime, date, time as dtime
from importlib.machinery import SourceFileLoader
from importlib import util as importlib_util

# Ensure the installed 'mcp' SDK package is imported instead of the local 'mcp.py'
# by moving the CWD placeholder ('') or script directory to the end of sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
try:
    if sys.path:
        # If the first path is '' (CWD) or the script directory, move it to the end
        if sys.path[0] in ("", _script_dir):
            sys.path = sys.path[1:] + [sys.path[0]]
        # Also ensure the explicit script directory (if present elsewhere) is de-prioritized
        elif _script_dir in sys.path:
            sys.path.remove(_script_dir)
            sys.path.append(_script_dir)
except Exception:
    # If anything goes wrong, continue — worst case the import below will fail as before
    pass

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions


# Helpers
def _to_bool(value: Any, default: bool = False) -> bool:
    """Best-effort boolean coercion for loose client inputs.

    Accepts real booleans, common string variants (true/false/1/0/yes/no/on/off,
    t/f/y/n) case-insensitively, and integers 0/1. Falls back to `default`.
    """
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            # Only treat exact 0/1 as booleans to avoid surprising casts
            if value == 1:
                return True
            if value == 0:
                return False
            return default
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "on", "t", "y"}:
                return True
            if v in {"false", "0", "no", "off", "f", "n"}:
                return False
            return default
    except Exception:
        pass
    return default


# Load the existing action-based tool implementation without modifying it
_wrapper_path = os.path.join(_script_dir, "mcp.py")
_loader = SourceFileLoader("kqc_wrapper", _wrapper_path)
_spec = importlib_util.spec_from_loader(_loader.name, _loader)
kqc_wrapper = importlib_util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(kqc_wrapper)  # type: ignore[attr-defined]


server = Server("kusto-query-cli")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Expose supported actions as MCP tools."""
    return [
        types.Tool(
            name="AUTH_STATUS",
            description="Check Azure CLI authentication status",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        types.Tool(
            name="LOGIN",
            description="Start device-code login flow (optional subscription_id)",
            inputSchema={
                "type": "object",
                "properties": {"subscription_id": {"type": ["string", "null"]}},
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="LOGOUT",
            description="Logout Azure CLI session",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        types.Tool(
            name="LIST_SUBSCRIPTIONS",
            description="List accessible subscriptions (optional subscription_id)",
            inputSchema={
                "type": "object",
                "properties": {"subscription_id": {"type": ["string", "null"]}},
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="QUERY",
            description="Run a Kusto query against a cluster/database",
            inputSchema={
                "type": "object",
                "properties": {
                    # Align with schemas/actions/QUERY.request.schema.json
                    "cluster_url": {"type": "string", "format": "uri"},
                    "database": {"type": "string"},
                    "query": {"type": "string"},
                    "socks5_proxy": {"type": "string"},
                    # Be lenient for clients that send 1/0 or strings; we coerce server-side
                    "socks5_dns": {
                        "oneOf": [
                            {"type": "boolean"},
                            {"type": "integer", "enum": [0, 1]},
                            {
                                "type": "string",
                                "enum": [
                                    "true",
                                    "false",
                                    "1",
                                    "0",
                                    "yes",
                                    "no",
                                    "on",
                                    "off",
                                    "t",
                                    "f",
                                    "y",
                                    "n",
                                ],
                            },
                        ],
                        "default": False,
                        "description": "Whether to use the SOCKS5 proxy for DNS resolution (BOOLEAN). Accepts: true/false/1/0/yes/no/on/off (case-insensitive).",
                    },
                },
                "required": ["cluster_url", "database", "query"],
                "additionalProperties": False,
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]):
    """Dispatch MCP tool calls to the existing action handlers."""
    start = time.time()
    
    def _json_sanitize(value: Any) -> Any:
        """Recursively convert values to JSON-serializable types.

        Handles datetime/date/time, pandas.Timestamp, NumPy scalars/arrays,
        UUID, and generic mappings/sequences.
        """
        # Fast-path for primitives
        if value is None or isinstance(value, (bool, int, float, str)):
            return value

        # Datetime-like
        if isinstance(value, (datetime, date, dtime)):
            try:
                return value.isoformat()
            except Exception:
                return str(value)

        # pandas.Timestamp without importing pandas eagerly
        try:
            # pandas.Timestamp has an attribute 'to_pydatetime' and 'isoformat'
            # Check by duck-typing to avoid hard dep if pandas isn't installed
            if hasattr(value, "isoformat") and value.__class__.__name__ == "Timestamp":
                return value.isoformat()
        except Exception:
            pass

        # NumPy types (scalars/arrays)
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

        # UUID
        try:
            import uuid as _uuid  # local name to avoid shadowing
            if isinstance(value, _uuid.UUID):
                return str(value)
        except Exception:
            pass

        # Bytes -> UTF-8 if possible, else base64
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8")
            except Exception:
                import base64
                return base64.b64encode(bytes(value)).decode("ascii")

        # Sets/Tuples -> lists
        if isinstance(value, (set, tuple)):
            return [_json_sanitize(v) for v in value]

        # Mappings
        if isinstance(value, dict):
            return {str(k): _json_sanitize(v) for k, v in value.items()}

        # Iterables (lists already fine)
        if isinstance(value, list):
            return [_json_sanitize(v) for v in value]

        # Fallback: best-effort string
        try:
            return str(value)
        except Exception:
            return None
    try:
        if name == "AUTH_STATUS":
            env = kqc_wrapper.handle_auth_status(start)
        elif name == "LOGIN":
            env = kqc_wrapper.handle_login(start, arguments.get("subscription_id"))
        elif name == "LOGOUT":
            env = kqc_wrapper.handle_logout(start)
        elif name == "LIST_SUBSCRIPTIONS":
            env = kqc_wrapper.handle_list_subscriptions(start, arguments.get("subscription_id"))
        elif name == "QUERY":
            env = kqc_wrapper.handle_query(
                {
                    # Forward arguments using the key names expected by the wrapper
                    "cluster_url": arguments.get("cluster_url"),
                    "database": arguments.get("database"),
                    "query": arguments.get("query"),
                    "socks5_proxy": arguments.get("socks5_proxy"),
                    # Coerce various representations to a strict boolean expected by the wrapper
                    "socks5_dns": _to_bool(arguments.get("socks5_dns"), False),
                },
                start,
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

        # Pass through data on success; surface errors as MCP errors
        if env.get("status") == "success":
            # Ensure the data we pass to the MCP SDK is JSON-serializable
            data = env.get("data", {})
            return _json_sanitize(data)
        raise RuntimeError((env.get("error") or {}).get("message", "Tool failed"))
    except Exception as e:
        # Minimal logging to stderr for diagnostics without polluting stdio channel
        try:
            print(f"mcp-sdk server: tool '{name}' failed: {e}", file=sys.stderr)
        except Exception:
            pass
        raise


async def run() -> None:
    version = kqc_wrapper.load_version()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="kusto-query-cli",
                server_version=version,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())
