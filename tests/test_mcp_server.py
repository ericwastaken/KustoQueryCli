import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

from mcp.client import Client
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
QUERY = {
    "cluster_url": "https://help.kusto.windows.net",
    "database": "Samples",
    "query": "print value=1",
}


class MCPAdapterTests(unittest.IsolatedAsyncioTestCase):


    def setUp(self):
        spec = importlib.util.spec_from_file_location("kqc_server_test", ROOT / "mcp-stdio-server.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.wrapper = self.module.kqc_wrapper
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.wrapper.PROXY_CONFIG_FILE = str(Path(directory) / "proxy.json")
        self.wrapper.SUBSCRIPTIONS_CACHE_FILE = str(Path(directory) / "subscriptions.json")
        self.wrapper.is_azure_cli_installed = Mock(return_value=True)
        self.wrapper.is_authenticated = Mock(return_value=(False, {}))
        self.wrapper.run_command = Mock(side_effect=AssertionError("Unexpected Azure CLI command"))
        self.wrapper.execute_adx_query = Mock(return_value=[])
        self.enterContext(patch.dict(os.environ, {"MCP_AZURE_AUTH_MODE": "host_shared"}))


    def assert_success(self, result):
        self.assertFalse(result.is_error, result)
        self.assertIsInstance(result.structured_content, dict)
        self.assertEqual(json.loads(result.content[0].text), result.structured_content)
        return result.structured_content


    async def test_catalog_and_introspection_in_both_protocol_modes(self):
        version = (ROOT / "mcp-wrapper-version").read_text().strip()
        for mode in ("auto", "legacy"):
            with self.subTest(mode=mode):
                async with Client(self.module.server, mode=mode) as client:
                    listed = await client.list_tools()
                    self.assertEqual({tool.name for tool in listed.tools}, {
                        "AUTH_STATUS", "LOGIN", "LOGOUT", "LIST_SUBSCRIPTIONS",
                        "PROXY_CONFIG", "QUERY", "MANIFEST", "GET_SCHEMA", "GET_EXAMPLE",
                    })
                    manifest = self.assert_success(await client.call_tool("MANIFEST"))
                    self.assertEqual(manifest["version"], version)
                    schema = self.assert_success(await client.call_tool(
                        "GET_SCHEMA", {"path": "actions/QUERY.request.schema.json"}
                    ))
                    query_tool = next(tool for tool in listed.tools if tool.name == "QUERY")
                    self.assertEqual(query_tool.input_schema, schema["properties"]["params"])
                    for path in (ROOT / "examples").glob("*.json"):
                        example = self.assert_success(await client.call_tool("GET_EXAMPLE", {"name": path.name}))
                        self.assertEqual(example, json.loads(path.read_text()))
                        if "metadata" in example:
                            self.assertEqual(example["metadata"]["wrapper_version"], version)


    async def test_invalid_arguments_never_reach_dispatch(self):
        self.module.call_tool = AsyncMock()
        cases = [
            ("QUERY", {}),
            ("QUERY", {**QUERY, "query": 42}),
            ("QUERY", {**QUERY, "unexpected": True}),
            ("PROXY_CONFIG", {"clear": []}),
            ("GET_SCHEMA", {}),
            ("DOES_NOT_EXIST", {}),
        ]
        async with Client(self.module.server) as client:
            for name, arguments in cases:
                with self.subTest(name=name, arguments=arguments):
                    result = await client.call_tool(name, arguments)
                    self.assertTrue(result.is_error)
                    self.assertIsNone(result.structured_content)
                    self.assertTrue(result.content[0].text)
        self.module.call_tool.assert_not_awaited()


    async def test_query_serialization_preserves_text_and_structured_results(self):
        identifier = UUID("12345678-1234-1234-1234-123456789012")
        self.wrapper.execute_adx_query.return_value = pd.DataFrame([{
            "count": np.int64(7),
            "time": pd.Timestamp("2026-09-24T12:00:00Z"),
            "id": identifier,
        }])
        async with Client(self.module.server) as client:
            data = self.assert_success(await client.call_tool("QUERY", QUERY))
        self.assertEqual(data["row_count"], 1)
        self.assertEqual(data["result"], [{
            "count": 7, "time": "2026-09-24T12:00:00+00:00", "id": str(identifier),
        }])
        self.wrapper.execute_adx_query.assert_called_once_with(
            **QUERY, socks5_proxy=None, socks5_dns=False
        )


    async def test_execution_and_file_errors_remain_tool_results(self):
        self.wrapper.execute_adx_query.side_effect = RuntimeError("Cluster unavailable")
        async with Client(self.module.server) as client:
            for name, arguments, message in [
                ("QUERY", QUERY, "Cluster unavailable"),
                ("GET_SCHEMA", {"path": "../requirements.txt"}, "Schema not found"),
                ("GET_EXAMPLE", {"name": "missing.json"}, "Example not found"),
            ]:
                with self.subTest(name=name):
                    result = await client.call_tool(name, arguments)
                    self.assertTrue(result.is_error)
                    self.assertIn(message, result.content[0].text)


    async def test_host_shared_auth_tools_do_not_manage_host_login(self):
        async with Client(self.module.server) as client:
            status = self.assert_success(await client.call_tool("AUTH_STATUS"))
            self.assertFalse(status["authenticated"])
            self.assertEqual(status["azure_auth_mode"], "host_shared")
            login = self.assert_success(await client.call_tool("LOGIN"))
            self.assertTrue(login["login_required"])
            self.assertIn("az login", login["message"])
            logout = self.assert_success(await client.call_tool("LOGOUT"))
            self.assertFalse(logout["logged_out"])
            subscriptions = self.assert_success(await client.call_tool("LIST_SUBSCRIPTIONS"))
            self.assertTrue(subscriptions["login_required"])
        self.wrapper.run_command.assert_not_called()


    async def test_container_auth_and_subscription_dispatch(self):
        self.wrapper.is_authenticated.return_value = (True, {"user": "test"})
        self.wrapper.list_enabled_subscriptions = Mock(return_value=[{"id": "test-subscription"}])
        self.wrapper.select_subscription = Mock(return_value=(True, None))
        self.wrapper.run_command = Mock(return_value=(0, "", ""))
        subscription_id = "11111111-1111-1111-1111-111111111111"
        with patch.dict(os.environ, {"MCP_AZURE_AUTH_MODE": "container_managed"}):
            async with Client(self.module.server) as client:
                login = self.assert_success(await client.call_tool("LOGIN", {"subscription_id": subscription_id}))
                self.assertTrue(login["authenticated"])
                self.wrapper.select_subscription.assert_called_once_with(subscription_id)
                subscriptions = self.assert_success(await client.call_tool("LIST_SUBSCRIPTIONS"))
                self.assertEqual(subscriptions["subscriptions"], [{"id": "test-subscription"}])
                self.assertTrue(Path(self.wrapper.SUBSCRIPTIONS_CACHE_FILE).exists())
                logout = self.assert_success(await client.call_tool("LOGOUT"))
                self.assertTrue(logout["logged_out"])
                self.assertFalse(Path(self.wrapper.SUBSCRIPTIONS_CACHE_FILE).exists())
        self.wrapper.run_command.assert_called_once_with(["az", "logout", "--only-show-errors"])


    async def test_proxy_persists_across_sessions_and_clears(self):
        async with Client(self.module.server) as client:
            data = self.assert_success(await client.call_tool("PROXY_CONFIG", {
                "socks5_proxy": "proxy.internal:1080", "socks5_dns": "yes",
            }))
            self.assertTrue(data["socks5_dns"])
        self.assertTrue(Path(self.wrapper.PROXY_CONFIG_FILE).exists())
        async with Client(self.module.server) as client:
            self.assert_success(await client.call_tool("QUERY", QUERY))
            self.wrapper.execute_adx_query.assert_called_with(
                **QUERY, socks5_proxy="proxy.internal:1080", socks5_dns=True
            )
            self.assert_success(await client.call_tool("PROXY_CONFIG", {"clear": "true"}))
            self.assert_success(await client.call_tool("QUERY", QUERY))
            self.wrapper.execute_adx_query.assert_called_with(**QUERY, socks5_proxy=None, socks5_dns=False)
        self.assertFalse(Path(self.wrapper.PROXY_CONFIG_FILE).exists())


class ReleaseMetadataTests(unittest.TestCase):


    def test_release_metadata_is_consistent(self):
        version = (ROOT / "mcp-wrapper-version").read_text().strip()
        self.assertEqual(json.loads((ROOT / "mcp-manifest.json").read_text())["version"], version)
        self.assertIn(f"KUSTO_QUERY_CLI_VERSION={version}", (ROOT / ".env").read_text())
        for path in (ROOT / "examples").glob("*.json"):
            data = json.loads(path.read_text())
            if "metadata" in data:
                self.assertEqual(data["metadata"]["wrapper_version"], version, str(path))


if __name__ == "__main__":
    unittest.main()
