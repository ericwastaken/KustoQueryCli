import importlib.util
import os
import pathlib
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_wrapper_module():
    from kusto_query_cli.core import auth, proxy
    from kusto_query_cli.mcp import actions
    importlib.reload(auth)
    importlib.reload(proxy)
    return importlib.reload(actions)



class ProxyConfigTests(unittest.TestCase):


    def test_auth_status_reports_host_shared_auth_mode(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (True, {"user": "tester", "environment": "AzureCloud"})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")
            old_mode = os.environ.get("MCP_AZURE_AUTH_MODE")
            os.environ["MCP_AZURE_AUTH_MODE"] = "host_shared"
            try:
                env = wrapper.handle_auth_status(time.time())
            finally:
                if old_mode is None:
                    os.environ.pop("MCP_AZURE_AUTH_MODE", None)
                else:
                    os.environ["MCP_AZURE_AUTH_MODE"] = old_mode

            self.assertEqual(env["status"], "success")
            self.assertEqual(env["data"]["azure_auth_mode"], "host_shared")
            self.assertIn("shared from the host", env["data"]["message"])


    def test_login_in_host_shared_mode_instructs_host_login(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (False, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")
            old_mode = os.environ.get("MCP_AZURE_AUTH_MODE")
            os.environ["MCP_AZURE_AUTH_MODE"] = "host_shared"
            try:
                env = wrapper.handle_login(time.time(), "11111111-1111-1111-1111-111111111111")
            finally:
                if old_mode is None:
                    os.environ.pop("MCP_AZURE_AUTH_MODE", None)
                else:
                    os.environ["MCP_AZURE_AUTH_MODE"] = old_mode

            self.assertEqual(env["status"], "success")
            self.assertFalse(env["data"]["authenticated"])
            self.assertTrue(env["data"]["login_required"])
            self.assertEqual(env["data"]["azure_auth_mode"], "host_shared")
            self.assertIn("az login", env["data"]["message"])
            self.assertEqual(
                env["data"]["requested_subscription_id"],
                "11111111-1111-1111-1111-111111111111",
            )
            self.assertNotIn("verification_url", env["data"])
            self.assertNotIn("device_code", env["data"])


    def test_logout_in_host_shared_mode_instructs_host_logout(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (True, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")
            old_mode = os.environ.get("MCP_AZURE_AUTH_MODE")
            os.environ["MCP_AZURE_AUTH_MODE"] = "host_shared"
            try:
                env = wrapper.handle_logout(time.time())
            finally:
                if old_mode is None:
                    os.environ.pop("MCP_AZURE_AUTH_MODE", None)
                else:
                    os.environ["MCP_AZURE_AUTH_MODE"] = old_mode

            self.assertEqual(env["status"], "success")
            self.assertFalse(env["data"]["logged_out"])
            self.assertEqual(env["data"]["azure_auth_mode"], "host_shared")
            self.assertIn("az logout", env["data"]["message"])


    def test_list_subscriptions_in_host_shared_mode_requires_host_login(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (False, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = pathlib.Path(tmpdir) / "mcp_subscriptions_cache.json"
            wrapper.auth.SUBSCRIPTIONS_CACHE_FILE = str(cache_path)
            cache_path.write_text(
                '{"subscriptions":[{"id":"11111111-1111-1111-1111-111111111111","name":"Test","tenant_id":"22222222-2222-2222-2222-222222222222","state":"Enabled"}]}',
                encoding="utf-8",
            )
            old_mode = os.environ.get("MCP_AZURE_AUTH_MODE")
            os.environ["MCP_AZURE_AUTH_MODE"] = "host_shared"
            try:
                env = wrapper.handle_list_subscriptions(
                    time.time(),
                    "33333333-3333-3333-3333-333333333333",
                )
            finally:
                if old_mode is None:
                    os.environ.pop("MCP_AZURE_AUTH_MODE", None)
                else:
                    os.environ["MCP_AZURE_AUTH_MODE"] = old_mode

            self.assertEqual(env["status"], "success")
            self.assertTrue(env["data"]["login_required"])
            self.assertEqual(env["data"]["azure_auth_mode"], "host_shared")
            self.assertIn("shared from the host", env["data"]["message"])
            self.assertEqual(len(env["data"]["subscriptions"]), 1)


    def test_auth_status_includes_proxy_config(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (True, {"user": "tester", "environment": "AzureCloud"})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")

            wrapper.handle_proxy_config(
                {"socks5_proxy": "proxy.internal:1080", "socks5_dns": True},
                time.time(),
            )

            env = wrapper.handle_auth_status(time.time())

            self.assertEqual(env["status"], "success")
            self.assertEqual(env["data"]["proxy_config"]["socks5_proxy"], "proxy.internal:1080")
            self.assertIs(env["data"]["proxy_config"]["socks5_dns"], True)


    def test_proxy_config_persists_for_subsequent_queries(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (True, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")

            captured = {}


            def fake_execute_adx_query(**kwargs):
                captured.update(kwargs)
                return []

            wrapper.execute_adx_query = fake_execute_adx_query

            proxy_env = wrapper.handle_proxy_config(
                {"socks5_proxy": "proxy.internal:1080", "socks5_dns": "true"},
                time.time(),
            )

            self.assertEqual(proxy_env["status"], "success")
            self.assertEqual(
                proxy_env["data"],
                {
                    "proxy_enabled": True,
                    "socks5_proxy": "proxy.internal:1080",
                    "socks5_dns": True,
                },
            )

            proxy_path = wrapper.proxy.PROXY_CONFIG_FILE
            reloaded = load_wrapper_module()
            reloaded.proxy.PROXY_CONFIG_FILE = proxy_path
            reloaded.auth.is_azure_cli_installed = lambda _: True
            reloaded.auth.is_authenticated = lambda: (True, {})
            reloaded.execute_adx_query = fake_execute_adx_query

            query_env = reloaded.handle_query(
                {
                    "cluster_url": "https://help.kusto.windows.net",
                    "database": "Samples",
                    "query": "StormEvents | take 1",
                },
                time.time(),
            )

            self.assertEqual(query_env["status"], "success")
            self.assertEqual(captured["socks5_proxy"], "proxy.internal:1080")
            self.assertIs(captured["socks5_dns"], True)


    def test_proxy_config_clear_removes_persisted_proxy(self):
        wrapper = load_wrapper_module()
        wrapper.auth.is_azure_cli_installed = lambda _: True
        wrapper.auth.is_authenticated = lambda: (True, {})
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper.proxy.PROXY_CONFIG_FILE = str(pathlib.Path(tmpdir) / "mcp_proxy_config.json")

            calls = []


            def fake_execute_adx_query(**kwargs):
                calls.append(kwargs)
                return []

            wrapper.execute_adx_query = fake_execute_adx_query

            wrapper.handle_proxy_config(
                {"socks5_proxy": "proxy.internal:1080", "socks5_dns": True},
                time.time(),
            )

            cleared_env = wrapper.handle_proxy_config(
                {"clear": True},
                time.time(),
            )

            self.assertEqual(
                cleared_env["data"],
                {
                    "proxy_enabled": False,
                    "socks5_proxy": None,
                    "socks5_dns": False,
                },
            )
            self.assertFalse(pathlib.Path(wrapper.proxy.PROXY_CONFIG_FILE).exists())

            query_env = wrapper.handle_query(
                {
                    "cluster_url": "https://help.kusto.windows.net",
                    "database": "Samples",
                    "query": "StormEvents | take 1",
                },
                time.time(),
            )

            self.assertEqual(query_env["status"], "success")
            self.assertIsNone(calls[-1]["socks5_proxy"])
            self.assertIs(calls[-1]["socks5_dns"], False)


if __name__ == "__main__":
    unittest.main()
