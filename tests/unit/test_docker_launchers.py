"""Exercise public launchers with a fake Docker executable, without a daemon."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
REMOTE_IMAGE = "ghcr.io/example/kustoquerycli@sha256:" + "a" * 64


class DockerLauncherTests(unittest.TestCase):


    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="kqc-launchers-")))
        self.log = self.directory / "docker.jsonl"
        executable = self.directory / "docker"
        executable.write_text(f"#!{sys.executable}\n" + '''import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["MOCK_DOCKER_LOG"], "a") as stream:
    stream.write(json.dumps({"args": args, "image": os.environ.get("KQC_RUNTIME_IMAGE"), "cwd": os.getcwd()}) + "\\n")
if args[:2] == ["image", "inspect"]:
    sys.exit(0 if os.environ.get("MOCK_IMAGE_PRESENT") == "1" else 1)
if args[0] in ("build", "pull"):
    print("Docker acquisition progress")
    sys.exit(int(os.environ.get("MOCK_ACQUIRE_STATUS", "0")))
if args[0] in ("run", "compose"):
    print("runtime-output")
    sys.exit(int(os.environ.get("MOCK_RUN_STATUS", "0")))
sys.exit("Unexpected Docker command: " + repr(args))
''')
        executable.chmod(0o755)
        self.environment = {key: value for key, value in os.environ.items() if key not in {
            "KQC_IMAGE", "KQC_RUNTIME_IMAGE", "KUSTO_QUERY_CLI_VERSION", "AZURE_STATE_VOLUME",
            "MCP_CONTAINER_NAME", "MCP_LOG_LEVEL", "MCP_LOG_PAYLOADS",
        }}
        self.environment.update({
            "PATH": str(self.directory) + os.pathsep + os.environ.get("PATH", ""),
            "MOCK_DOCKER_LOG": str(self.log),
        })


    def launch(self, script, *args, **environment):
        return subprocess.run(
            ["/bin/bash", str(ROOT / script), *args], cwd=self.directory,
            env={**self.environment, **environment}, capture_output=True, text=True,
            timeout=20,
        )


    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []


    def test_missing_external_image_is_pulled_and_exact_reference_runs(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, KQC_IMAGE=REMOTE_IMAGE)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertEqual(calls[0]["args"], ["image", "inspect", REMOTE_IMAGE])
                self.assertEqual(calls[1]["args"], ["pull", REMOTE_IMAGE])
                self.assertNotIn("build", [call["args"][0] for call in calls])
                if script == "docker-mcp.sh":
                    self.assertIn(REMOTE_IMAGE, calls[-1]["args"])
                else:
                    self.assertEqual(calls[-1]["image"], REMOTE_IMAGE)
                    self.assertIn(str(ROOT / "docker-compose.yml"), calls[-1]["args"])
                    self.assertEqual(calls[-1]["args"][calls[-1]["args"].index("--pull") + 1], "never")
                    self.assertEqual(calls[-1]["cwd"], str(ROOT))
                self.assertEqual(result.stdout, "runtime-output\n")


    def test_cached_external_image_never_pulls_or_builds(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, KQC_IMAGE=REMOTE_IMAGE, MOCK_IMAGE_PRESENT="1")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(self.calls()), 2)


    def test_failed_external_pull_stops_without_building_or_running(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, KQC_IMAGE=REMOTE_IMAGE, MOCK_ACQUIRE_STATUS="1")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([call["args"][0] for call in self.calls()], ["image", "pull"])
                self.assertEqual(result.stdout, "")


    def test_explicit_image_rejects_force_and_local_build_entrypoint(self):
        for script, args in (
            ("docker-mcp.sh", ["--force"]), ("docker-run.sh", ["--force", "az", "version"]),
            ("docker-mcp-build.sh", []),
        ):
            with self.subTest(script=script):
                result = self.launch(script, *args, KQC_IMAGE=REMOTE_IMAGE)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("KQC_IMAGE", result.stderr)
                self.assertEqual(self.calls(), [])


    def test_local_missing_image_builds_and_preserves_clean_stdout(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, KUSTO_QUERY_CLI_VERSION="9.8.7")
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertEqual(calls[1]["args"], ["build", "-t", "kusto-query-cli:9.8.7", "."])
                self.assertEqual(result.stdout, "runtime-output\n")


    def test_failed_local_build_stops_launcher(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, MOCK_ACQUIRE_STATUS="1")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([call["args"][0] for call in self.calls()], ["image", "build"])


    def test_force_rebuilds_cached_local_image_without_removing_it(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, "--force", MOCK_IMAGE_PRESENT="1")
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [call["args"][0] for call in self.calls()]
                self.assertIn("build", commands)
                self.assertNotIn("rmi", commands)


    def test_mcp_mounts_and_stdio_survive_both_acquisition_modes(self):
        for image in ("", REMOTE_IMAGE):
            for shared in (False, True):
                with self.subTest(image=image, shared=shared):
                    self.log.unlink(missing_ok=True)
                    flags = ["--share-host-azure-state"] if shared else []
                    result = self.launch(
                        "docker-mcp.sh", *flags, "argument with spaces", KQC_IMAGE=image,
                        MOCK_IMAGE_PRESENT="1", AZURE_STATE_VOLUME="custom-auth",
                        MCP_CONTAINER_NAME="test-session", MCP_LOG_LEVEL="ERROR",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    args = self.calls()[-1]["args"]
                    self.assertIn("-i", args)
                    self.assertNotIn("-t", args)
                    mount = str(Path.home() / ".azure") if shared else "custom-auth"
                    self.assertEqual(args[args.index("-v") + 1], mount + ":/root/.azure")
                    mode = "host_shared" if shared else "container_managed"
                    self.assertIn("MCP_AZURE_AUTH_MODE=" + mode, args)
                    self.assertIn("MCP_LOG_LEVEL=ERROR", args)
                    self.assertEqual(args[args.index("--name") + 1], "test-session")
                    self.assertEqual(args[-3:], ["python", "mcp-stdio-server.py", "argument with spaces"])


    def test_default_mcp_auth_volume_is_stable(self):
        result = self.launch("docker-mcp.sh", MOCK_IMAGE_PRESENT="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kusto-query-cli-mcp-azure-state:/root/.azure", self.calls()[-1]["args"])


    def test_cli_down_does_not_acquire_image_and_preserves_exit_status(self):
        result = self.launch("docker-run.sh", "down", "--volumes", KQC_IMAGE=REMOTE_IMAGE, MOCK_RUN_STATUS="7")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0]["args"][-2:], ["down", "--volumes"])


    def test_runtime_exit_status_and_cli_arguments_are_preserved(self):
        for script in ("docker-mcp.sh", "docker-run.sh"):
            with self.subTest(script=script):
                self.log.unlink(missing_ok=True)
                result = self.launch(script, "python", "file with spaces.py", MOCK_IMAGE_PRESENT="1", MOCK_RUN_STATUS="23")
                self.assertEqual(result.returncode, 23)
                self.assertEqual(self.calls()[-1]["args"][-2:], ["python", "file with spaces.py"])


if __name__ == "__main__":
    unittest.main()
