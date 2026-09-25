"""Check the existing 1.x public MCP contract without imposing v2 adapter changes."""

import asyncio
from importlib.metadata import version
import json
import os
import sys

from mcp.client.stdio import StdioServerParameters, stdio_client


SDK_MAJOR = int(version("mcp").split(".")[0])


async def check(client, expected):
    listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == {
        "AUTH_STATUS", "LOGIN", "LOGOUT", "LIST_SUBSCRIPTIONS", "PROXY_CONFIG",
        "QUERY", "MANIFEST", "GET_SCHEMA", "GET_EXAMPLE",
    }, listed
    for name, arguments in (
        ("MANIFEST", {}),
        ("GET_SCHEMA", {"path": "actions/QUERY.request.schema.json"}),
        ("GET_EXAMPLE", {"name": "QUERY.success.json"}),
    ):
        result = await client.call_tool(name, arguments)
        assert not (result.is_error if SDK_MAJOR >= 2 else result.isError), result
        data = json.loads(result.content[0].text)
        assert isinstance(data, dict) and data, data
        if name == "MANIFEST":
            assert data["version"] == expected, data
        if name == "GET_EXAMPLE":
            assert data["metadata"]["wrapper_version"] == expected, data


async def main():
    expected, *command = sys.argv[1:]
    params = StdioServerParameters(command=command[0], args=command[1:],
                                   env={**os.environ, "MCP_LOG_LEVEL": "CRITICAL"})
    if SDK_MAJOR >= 2:
        from mcp.client import Client
        for mode in ("auto", "legacy"):
            async with asyncio.timeout(60):
                async with Client(params, mode=mode) as client:
                    assert client.server_info.version == expected
                    await check(client, expected)
                    print(f"MCP {version('mcp')} {mode}: passed")
    else:
        from mcp import ClientSession
        async with asyncio.timeout(60):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    initialized = await client.initialize()
                    assert initialized.serverInfo.version == expected
                    await check(client, expected)
                    print(f"MCP {version('mcp')} legacy: passed")


if __name__ == "__main__":
    asyncio.run(main())
