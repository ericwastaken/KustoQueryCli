"""Exercise the preserved launchers and extracted services without live Azure access."""
import asyncio
import contextlib
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid

import pandas as pd

from kusto_query_cli import resources
from kusto_query_cli.cli import runner
from kusto_query_cli.core import auth, proxy, query
from kusto_query_cli.mcp import actions

ROOT = Path(__file__).resolve().parents[2]


class PythonEntrypointTests(unittest.TestCase):


    def test_cli_launchers_preserve_query_sources_and_output_formats(self):
        frame = pd.DataFrame([{"name": "alpha, beta", "count": 7}])
        with tempfile.TemporaryDirectory() as directory:
            query_file = Path(directory) / "query.kql"
            query_file.write_text("Events | take 1", encoding="utf-8")
            cases = [
                ("k2json.py", ["--query", "Events | take 1"], "ignored stdin", "json"),
                ("k2csv.py", ["--queryFile", str(query_file)], "ignored stdin", "csv"),
                ("k2json.py", [], "  Events | take 1\n", "json"),
            ]
            for script, source_args, stdin, output_format in cases:
                with self.subTest(script=script, source_args=source_args):
                    output = io.StringIO()
                    argv = [script, "--database", "test-db", "--adxUrl", "https://example.invalid"] + source_args
                    with (
                        contextlib.chdir(directory),
                        mock.patch.object(sys, "argv", argv),
                        mock.patch.object(sys, "stdin", io.StringIO(stdin)),
                        contextlib.redirect_stdout(output),
                        mock.patch.object(runner, "check_azure_cli_logged_in") as check_auth,
                        mock.patch.object(runner, "execute_adx_query", return_value=frame) as execute,
                    ):
                        runpy.run_path(str(ROOT / script), run_name="__main__")
                    check_auth.assert_called_once_with()
                    execute.assert_called_once_with("https://example.invalid", "test-db", "Events | take 1")
                    if output_format == "json":
                        self.assertEqual(json.loads(output.getvalue()), [{"name": "alpha, beta", "count": 7}])
                    else:
                        self.assertEqual(list(csv.DictReader(io.StringIO(output.getvalue()))),
                                         [{"name": "alpha, beta", "count": "7"}])


    def test_cli_help_launches_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for script in ("k2json.py", "k2csv.py"):
                with self.subTest(script=script):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / script), "--help"],
                        cwd=directory, capture_output=True, text=True, timeout=20, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("--queryFile", result.stdout)
                    self.assertIn("--adxUrl", result.stdout)


    def test_one_shot_query_preserves_envelope_and_serialization(self):
        identifier = uuid.UUID("28ecff3a-5b63-458d-a51a-5b62e45c88c2")
        timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        request = {"action": "QUERY", "params": {
            "cluster_url": "https://example.invalid", "database": "test-db", "query": "Events | take 1",
        }}
        frame = pd.DataFrame([{"id": identifier, "when": timestamp}])
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with (
                contextlib.chdir(directory),
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(request))),
                contextlib.redirect_stdout(output),
                mock.patch.object(auth, "is_azure_cli_installed", return_value=True),
                mock.patch.object(auth, "is_authenticated", return_value=(True, {})),
                mock.patch.object(proxy, "PROXY_CONFIG_FILE", str(Path(directory) / "absent-proxy.json")),
                mock.patch.object(actions, "execute_adx_query", return_value=frame) as execute,
            ):
                runpy.run_path(str(ROOT / "mcp-wrapper.py"), run_name="__main__")
        response = json.loads(output.getvalue())
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["action"], "QUERY")
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"], {
            "row_count": 1, "result": [{"id": str(identifier), "when": timestamp.isoformat()}],
        })
        self.assertTrue(response["metadata"]["authenticated"])
        self.assertEqual(response["metadata"]["wrapper_version"], resources.load_version())
        self.assertEqual(response["metadata"]["protocol_version"], resources.load_protocol_version())
        uuid.UUID(response["metadata"]["request_id"])
        execute.assert_called_once_with(**request["params"], socks5_proxy=None, socks5_dns=False)


    def test_one_shot_errors_remain_json_envelopes(self):
        cases = [
            ("not-json", True, "JSON_PARSE_ERROR"),
            ('{"action":"UNKNOWN"}', True, "UNKNOWN_ACTION"),
            ('{"action":"AUTH_STATUS"}', False, "AZ_CLI_NOT_FOUND"),
        ]
        for payload, installed, error_code in cases:
            with self.subTest(error_code=error_code):
                output = io.StringIO()
                with (
                    mock.patch.object(sys, "stdin", io.StringIO(payload)),
                    contextlib.redirect_stdout(output),
                    mock.patch.object(auth, "is_azure_cli_installed", return_value=installed),
                    mock.patch.object(auth, "run_command") as run_command,
                ):
                    runpy.run_path(str(ROOT / "mcp-wrapper.py"), run_name="__main__")
                response = json.loads(output.getvalue())
                self.assertEqual(response["status"], "error")
                self.assertEqual(response["error"]["code"], error_code)
                run_command.assert_not_called()


    def test_manual_helpers_resolve_the_repository_after_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.chdir(directory), mock.patch("subprocess.Popen") as start_process:
                for script in sorted((ROOT / "tests/manual").glob("test-mcp-stdio-server*.py")):
                    with self.subTest(script=script.name):
                        namespace = runpy.run_path(str(script), run_name="manual_helper_path_test")
                        self.assertEqual(Path(namespace["ROOT"]), ROOT)
                        self.assertTrue((Path(namespace["ROOT"]) / "mcp-stdio-server.py").is_file())
                start_process.assert_not_called()


    def test_mcp_resources_resolve_outside_repository(self):
        from kusto_query_cli.mcp import server

        with tempfile.TemporaryDirectory() as directory:
            with contextlib.chdir(directory), mock.patch.object(auth, "is_authenticated", return_value=(False, {})):
                manifest = actions.handle_manifest(0)
                tools = asyncio.run(server.list_tools())
                schema = asyncio.run(server.call_tool("GET_SCHEMA", {"path": "actions/QUERY.request.schema.json"}))
                example = asyncio.run(server.call_tool("GET_EXAMPLE", {"name": "QUERY.request.json"}))
                self.assertEqual(resources.load_version(), (ROOT / "mcp-wrapper-version").read_text().strip())
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["data"], json.loads((ROOT / "mcp-manifest.json").read_text()))
        query_tool = next(tool for tool in tools if tool.name == "QUERY")
        self.assertEqual(query_tool.input_schema, schema["properties"]["params"])
        self.assertEqual(example, json.loads((ROOT / "examples/QUERY.request.json").read_text()))


    def test_shared_query_restores_proxy_environment_after_success_or_failure(self):
        proxy_keys = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
        frame = pd.DataFrame([{"count": 1}])
        for fails in (False, True):
            with self.subTest(fails=fails):


                def execute(database, statement):
                    self.assertEqual(database, "test-db")
                    self.assertEqual(statement, "Events | count")
                    self.assertEqual({os.environ.get(key) for key in proxy_keys}, {"socks5h://proxy.example:1080"})
                    if fails:
                        raise RuntimeError("simulated query failure")
                    return mock.Mock(primary_results=["result-table"])

                with (
                    mock.patch.dict(os.environ, {"HTTPS_PROXY": "https://existing-proxy", "ALL_PROXY": "socks5://existing"}, clear=True),
                    mock.patch.object(query.KustoConnectionStringBuilder, "with_az_cli_authentication", return_value="connection") as build,
                    mock.patch.object(query, "KustoClient") as client,
                    mock.patch.object(query, "dataframe_from_result_table", return_value=frame),
                ):
                    before = dict(os.environ)
                    client.return_value.execute.side_effect = execute
                    args = {
                        "cluster_url": "https://example.invalid", "database": "test-db", "query": "Events | count",
                        "socks5_proxy": "proxy.example:1080", "socks5_dns": True,
                    }
                    if fails:
                        with self.assertRaisesRegex(RuntimeError, "simulated query failure"):
                            query.execute_adx_query(**args)
                    else:
                        self.assertIs(query.execute_adx_query(**args), frame)
                    build.assert_called_once_with("https://example.invalid")
                    self.assertEqual(dict(os.environ), before)


if __name__ == "__main__":
    unittest.main()
