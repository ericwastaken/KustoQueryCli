import asyncio
import os
import sys
import time
import json
import logging
import uuid
from typing import Any, Optional

import mcp.server.stdio
import mcp.types as types
import jsonschema
from mcp.server import Server, ServerRequestContext
from kusto_query_cli.mcp import actions as kqc_wrapper
from kusto_query_cli.core.proxy import _to_bool
from kusto_query_cli.core.serialization import _json_sanitize
from kusto_query_cli.resources import ROOT

_script_dir = str(ROOT)


# ---- Logging setup ----


def _init_logging() -> logging.Logger:
    """Initialize a stderr logger for the MCP server.

    Controlled via environment variables:
    - MCP_LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
    - MCP_LOG_PAYLOADS: true/false to include full tool arguments/results at DEBUG level (default: false)
    """
    level_str = os.environ.get("MCP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    logger = logging.getLogger("mcp_stdio_server")
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        fmt = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


_LOGGER = _init_logging()


async def list_tools() -> list[types.Tool]:
    """Expose supported actions as MCP tools using canonical JSON Schemas and Examples."""
    _LOGGER.debug("list_tools called")


    def _schema_params_for(action: str) -> dict:
        """Load the canonical request schema for an action and return its `params` schema.

        Falls back to an empty object schema if the file is missing or invalid.
        """
        try:
            schema_path = os.path.join(_script_dir, "schemas", "actions", f"{action}.request.schema.json")
            with open(schema_path, "r", encoding="utf-8") as f:
                root = json.load(f)
            params = (root.get("properties") or {}).get("params")
            if isinstance(params, dict):
                # Ensure it's a JSON Schema object
                return params
        except Exception:
            pass
        return {"type": "object", "properties": {}, "additionalProperties": False}


    def _example_hint_for(action: str) -> Optional[str]:
        """Return an examples/<ACTION>.* file hint if present to guide clients."""
        try:
            ex_dir = os.path.join(_script_dir, "examples")
            if not os.path.isdir(ex_dir):
                return None
            prefix = action.upper()
            for name in sorted(os.listdir(ex_dir)):
                if name.upper().startswith(prefix):
                    return name
        except Exception:
            return None
        return None

    tools: list[types.Tool] = []

    # Core action tools
    for action, desc in [
        ("AUTH_STATUS", "Check Azure CLI authentication status"),
        ("LOGIN", "Start device-code login flow (optional subscription_id)"),
        ("LOGOUT", "Logout Azure CLI session"),
        ("LIST_SUBSCRIPTIONS", "List accessible subscriptions (optional subscription_id)"),
        ("PROXY_CONFIG", "Configure the default SOCKS5 proxy used by QUERY"),
        ("QUERY", "Run a Kusto query against a cluster/database"),
        ("MANIFEST", "Return the server capability manifest"),
    ]:
        hint = _example_hint_for(action)
        full_desc = desc if not hint else f"{desc} (see examples/{hint})"
        tools.append(
            types.Tool(
                name=action,
                description=full_desc,
                input_schema=_schema_params_for(action),
            )
        )

    # Introspection tools for schemas/examples to avoid duplicating information
    tools.append(
        types.Tool(
            name="GET_SCHEMA",
            description=(
                "Return a JSON Schema file content from the repository (request/response/action/global). "
                "Arguments: { path: string relative to schemas/ }"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path under schemas/"}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )
    tools.append(
        types.Tool(
            name="GET_EXAMPLE",
            description=(
                "Return an example JSON payload from the repository. Arguments: { name: string from examples/ }"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name under examples/"}
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        )
    )

    _LOGGER.info("list_tools returning %d tools", len(tools))
    return tools


async def call_tool(name: str, arguments: dict[str, Any]):
    """Dispatch MCP tool calls to the existing action handlers."""
    start = time.time()
    req_id = str(uuid.uuid4())

    # Configuration flags
    log_payloads = _to_bool(os.environ.get("MCP_LOG_PAYLOADS"), False)

    try:
        # Log request receipt
        summary_args = {k: ("***" if k.lower().endswith("token") else v) for k, v in (arguments or {}).items()}
        if log_payloads and _LOGGER.isEnabledFor(logging.DEBUG):
            try:
                _LOGGER.debug("[%s] call_tool received: %s args=%s", req_id, name, json.dumps(summary_args))
            except Exception:
                _LOGGER.debug("[%s] call_tool received: %s (args not JSON-serializable)", req_id, name)
        else:
            _LOGGER.info("[%s] call_tool received: %s", req_id, name)
        # High-level processing marker (visible at INFO); detailed flow at DEBUG
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("[%s] %s processing start", req_id, name)
        else:
            _LOGGER.info("[%s] %s processing", req_id, name)
    except Exception:
        # Never fail due to logging
        pass

    try:
        if name == "AUTH_STATUS":
            _LOGGER.debug("[%s] AUTH_STATUS start", req_id)
            env = kqc_wrapper.handle_auth_status(start)
        elif name == "LOGIN":
            _LOGGER.debug("[%s] LOGIN start", req_id)
            env = kqc_wrapper.handle_login(start, arguments.get("subscription_id"))
        elif name == "LOGOUT":
            _LOGGER.debug("[%s] LOGOUT start", req_id)
            env = kqc_wrapper.handle_logout(start)
        elif name == "LIST_SUBSCRIPTIONS":
            _LOGGER.debug("[%s] LIST_SUBSCRIPTIONS start", req_id)
            env = kqc_wrapper.handle_list_subscriptions(start, arguments.get("subscription_id"))
        elif name == "QUERY":
            if log_payloads and _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "[%s] QUERY params cluster_url=%s database=%s",
                    req_id,
                    arguments.get("cluster_url"),
                    arguments.get("database"),
                )
            env = kqc_wrapper.handle_query(
                {
                    "cluster_url": arguments.get("cluster_url"),
                    "database": arguments.get("database"),
                    "query": arguments.get("query"),
                },
                start,
            )
        elif name == "PROXY_CONFIG":
            if log_payloads and _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "[%s] PROXY_CONFIG params socks5_proxy=%s socks5_dns=%s clear=%s",
                    req_id,
                    arguments.get("socks5_proxy"),
                    _to_bool(arguments.get("socks5_dns"), False),
                    _to_bool(arguments.get("clear"), False),
                )
            proxy_args = {}
            if "socks5_proxy" in arguments:
                proxy_args["socks5_proxy"] = arguments.get("socks5_proxy")
            if "socks5_dns" in arguments:
                proxy_args["socks5_dns"] = _to_bool(arguments.get("socks5_dns"), False)
            if "clear" in arguments:
                proxy_args["clear"] = _to_bool(arguments.get("clear"), False)
            env = kqc_wrapper.handle_proxy_config(proxy_args, start)
        elif name == "MANIFEST":
            # Mirror MANIFEST behavior from wrapper for convenience (no params)
            _LOGGER.debug("[%s] MANIFEST start", req_id)
            env = kqc_wrapper.handle_manifest(start)
        elif name == "GET_SCHEMA":
            rel = str(arguments.get("path", "")).lstrip("/\\")
            if not rel:
                raise ValueError("Missing 'path' argument")
            base = os.path.join(_script_dir, "schemas")
            # Use absolute normalized paths and commonpath to prevent traversal or prefix tricks
            base_abs = os.path.abspath(base)
            target = os.path.normpath(os.path.join(base_abs, rel))
            target_abs = os.path.abspath(target)
            if os.path.commonpath([base_abs, target_abs]) != base_abs or not os.path.isfile(target_abs):
                raise FileNotFoundError(f"Schema not found: {rel}")
            _LOGGER.debug("[%s] GET_SCHEMA path=%s", req_id, rel)
            with open(target_abs, "r", encoding="utf-8") as f:
                result = json.load(f)
            # Structured completion + response markers
            try:
                dur_ms = int((time.time() - start) * 1000)
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s processed in %dms", req_id, name, dur_ms)
                else:
                    _LOGGER.info("[%s] %s processed in %dms", req_id, name, dur_ms)
            except Exception:
                pass
            # At INFO: just note response sent; at DEBUG: note response sent (payload logged separately if enabled)
            try:
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s response sent", req_id, name)
                    if log_payloads:
                        try:
                            _LOGGER.debug("[%s] %s result=%s", req_id, name, json.dumps(result))
                        except Exception:
                            _LOGGER.debug("[%s] %s result=<unserializable>", req_id, name)
                else:
                    _LOGGER.info("[%s] %s response sent", req_id, name)
            except Exception:
                pass
            return result
        elif name == "GET_EXAMPLE":
            fname = str(arguments.get("name", "")).lstrip("/\\")
            if not fname:
                raise ValueError("Missing 'name' argument")
            base = os.path.join(_script_dir, "examples")
            base_abs = os.path.abspath(base)
            target = os.path.normpath(os.path.join(base_abs, fname))
            target_abs = os.path.abspath(target)
            if os.path.commonpath([base_abs, target_abs]) != base_abs or not os.path.isfile(target_abs):
                raise FileNotFoundError(f"Example not found: {fname}")
            _LOGGER.debug("[%s] GET_EXAMPLE name=%s", req_id, fname)
            with open(target_abs, "r", encoding="utf-8") as f:
                result = json.load(f)
            # Structured completion + response markers
            try:
                dur_ms = int((time.time() - start) * 1000)
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s processed in %dms", req_id, name, dur_ms)
                else:
                    _LOGGER.info("[%s] %s processed in %dms", req_id, name, dur_ms)
            except Exception:
                pass
            try:
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s response sent", req_id, name)
                    if log_payloads:
                        try:
                            _LOGGER.debug("[%s] %s result=%s", req_id, name, json.dumps(result))
                        except Exception:
                            _LOGGER.debug("[%s] %s result=<unserializable>", req_id, name)
                else:
                    _LOGGER.info("[%s] %s response sent", req_id, name)
            except Exception:
                pass
            return result
        else:
            raise ValueError(f"Unknown tool: {name}")

        # Pass through data on success; surface errors as MCP errors
        if env.get("status") == "success":
            # Ensure the data we pass to the MCP SDK is JSON-serializable
            data = env.get("data", {})
            result = _json_sanitize(data)
            try:
                dur_ms = int((time.time() - start) * 1000)
                # Mark processing completion at both INFO/DEBUG
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s processed in %dms", req_id, name, dur_ms)
                else:
                    _LOGGER.info("[%s] %s processed in %dms", req_id, name, dur_ms)
                if log_payloads and _LOGGER.isEnabledFor(logging.DEBUG):
                    # Log the entire received envelope and result without truncation when payload logging is enabled
                    try:
                        _LOGGER.debug("[%s] %s envelope=%s", req_id, name, json.dumps(env))
                    except Exception:
                        # Fall back to a sanitized view if any non-JSON types slip through
                        try:
                            _LOGGER.debug("[%s] %s envelope=%s", req_id, name, json.dumps(_json_sanitize(env)))
                        except Exception:
                            _LOGGER.debug("[%s] %s envelope=<unserializable>", req_id, name)
                    _LOGGER.debug("[%s] %s success in %dms result=%s", req_id, name, dur_ms, json.dumps(result))
                else:
                    # Summarize size/type
                    size = None
                    try:
                        size = len(json.dumps(result))
                    except Exception:
                        pass
                    _LOGGER.info("[%s] %s success in %dms (result_size=%s)", req_id, name, dur_ms, size if size is not None else "n/a")
                # Final marker that the response was sent (regardless of payload logging)
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("[%s] %s response sent", req_id, name)
                else:
                    _LOGGER.info("[%s] %s response sent", req_id, name)
            except Exception:
                pass
            return result
        raise RuntimeError((env.get("error") or {}).get("message", "Tool failed"))
    except Exception as e:
        # Structured error logging to stderr without polluting stdio channel
        try:
            dur_ms = int((time.time() - start) * 1000)
            _LOGGER.exception("[%s] %s failed in %dms: %s", req_id, name, dur_ms, e)
        except Exception:
            pass
        raise


async def on_list_tools(
    ctx: ServerRequestContext, params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=await list_tools())


def _tool_error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        is_error=True,
    )


async def on_call_tool(
    ctx: ServerRequestContext, params: types.CallToolRequestParams
) -> types.CallToolResult:
    """Preserve the validation, result and error behavior of the MCP 1.x adapter."""
    try:
        tool = next((tool for tool in await list_tools() if tool.name == params.name), None)
        if tool is None:
            return _tool_error(f"Unknown tool: {params.name}")

        arguments = params.arguments or {}
        try:
            jsonschema.validate(instance=arguments, schema=tool.input_schema)
        except jsonschema.ValidationError as exc:
            return _tool_error(f"Input validation error: {exc.message}")

        data = await call_tool(params.name, arguments)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(data, indent=2))],
            structured_content=data,
            is_error=False,
        )
    except Exception as exc:
        # Tool failures must remain visible to the model, not become RPC errors.
        return _tool_error(str(exc))


server = Server(
    "kusto-query-cli",
    version=kqc_wrapper.load_version(),
    on_list_tools=on_list_tools,
    on_call_tool=on_call_tool,
)


async def run() -> None:
    version = kqc_wrapper.load_version()
    # Attempt to read protocol version for logging context
    proto_ver = None
    try:
        with open(os.path.join(_script_dir, "mcp-protocol-version"), "r", encoding="utf-8") as f:
            proto_ver = f.read().strip()
    except Exception:
        proto_ver = None

    _LOGGER.info(
        "Starting MCP stdio server name=%s version=%s protocol=%s python=%s",
        "kusto-query-cli",
        version,
        proto_ver or "unknown",
        sys.version.split()[0],
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        _LOGGER.info("MCP stdio streams established; server is ready to accept requests")
        try:
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
        finally:
            _LOGGER.info("Server.run has completed; shutting down")


if __name__ == "__main__":
    asyncio.run(run())
