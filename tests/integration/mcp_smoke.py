"""Exercise a real stdio server with either MCP 1.x or 2.x installed on the client.

Usage: python tests/integration/mcp_smoke.py [server command and arguments...]
No live Azure login or query is performed.
"""

import asyncio
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[2]
SDK_MAJOR = int(version("mcp").split(".")[0])
EXPECTED_VERSION = (ROOT / "mcp-wrapper-version").read_text().strip()


async def check(client):
    listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == {
        "AUTH_STATUS", "LOGIN", "LOGOUT", "LIST_SUBSCRIPTIONS", "PROXY_CONFIG",
        "QUERY", "MANIFEST", "GET_SCHEMA", "GET_EXAMPLE",
    }, listed
    for name, arguments, expect_error in [
        ("MANIFEST", {}, False),
        ("GET_SCHEMA", {"path": "actions/QUERY.request.schema.json"}, False),
        ("GET_EXAMPLE", {"name": "QUERY.success.json"}, False),
        ("QUERY", {}, True),
        ("GET_SCHEMA", {"path": "missing.json"}, True),
        ("UNKNOWN_TOOL", {}, True),
    ]:
        result = await client.call_tool(name, arguments)
        is_error = result.is_error if SDK_MAJOR >= 2 else result.isError
        assert is_error == expect_error, result
        if not expect_error:
            data = result.structured_content if SDK_MAJOR >= 2 else result.structuredContent
            assert data == json.loads(result.content[0].text), result
            if name == "MANIFEST":
                assert data["version"] == EXPECTED_VERSION, data
            if name == "GET_EXAMPLE":
                assert data["metadata"]["wrapper_version"] == EXPECTED_VERSION, data


async def main():
    command = sys.argv[1:] or [sys.executable, str(ROOT / "mcp-stdio-server.py")]
    with tempfile.TemporaryDirectory(prefix="kqc-smoke-azure-") as azure_config:
        params = StdioServerParameters(
            command=command[0], args=command[1:],
            env={**os.environ, "AZURE_CONFIG_DIR": azure_config, "MCP_LOG_LEVEL": "ERROR"},
        )
        if SDK_MAJOR >= 2:
            from mcp.client import Client
            for mode in ("auto", "legacy"):
                async with asyncio.timeout(60):
                    async with Client(params, mode=mode) as client:
                        assert client.server_info.version == EXPECTED_VERSION
                        await check(client)
                        print(f"MCP {version('mcp')} {mode}: passed ({client.protocol_version})")
        else:
            from mcp import ClientSession
            async with asyncio.timeout(60):
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as client:
                        initialized = await client.initialize()
                        assert initialized.serverInfo.version == EXPECTED_VERSION
                        await check(client)
                        print(f"MCP {version('mcp')} legacy client: passed")


if __name__ == "__main__":
    asyncio.run(main())
