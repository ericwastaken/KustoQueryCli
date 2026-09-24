"""Release checks shared by local preparation and GitHub Actions (stdlib only)."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent


class CheckFailure(RuntimeError):
    pass


def matrix(root=ROOT):
    return json.loads((root / "scripts/release-matrix.json").read_text())


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=4) + "\n")
    temporary.replace(path)


class Runner:


    def __init__(self, root, output):
        self.root = root
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.results = []


    def run(self, name, command, timeout=1200):
        logfile = self.output / f"{len(self.results) + 1:02d}-{name}.log"
        print(f"Checking {name} (log: {logfile})", flush=True)
        started = time.monotonic()
        result = {"name": name, "command": [str(part) for part in command], "log": str(logfile)}
        self.results.append(result)
        try:
            with logfile.open("w") as stream:
                process = subprocess.Popen(
                    result["command"], cwd=self.root, stdout=stream, stderr=subprocess.STDOUT,
                    start_new_session=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MCP_LOG_LEVEL": "CRITICAL"},
                )
                try:
                    code = process.wait(timeout=timeout)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise
            if code:
                raise CheckFailure(f"{name} failed (exit {code}); inspect {logfile}")
            result["status"] = "passed"
            return logfile.read_text()
        except BaseException:
            result["status"] = "failed"
            raise
        finally:
            result["seconds"] = round(time.monotonic() - started, 2)
            write_json(self.output / "checks.json", self.results)


def find_python(version):
    override = os.environ.get("KQC_PYTHON_" + version.replace(".", ""))
    candidate = override or shutil.which(f"python{version}")
    if not candidate and shutil.which("uv"):
        found = subprocess.run(
            ["uv", "python", "find", "--offline", version], capture_output=True, text=True, timeout=30,
        )
        if found.returncode == 0:
            candidate = found.stdout.strip()
    if not candidate:
        raise CheckFailure(f"Python {version} is required. Install it and add python{version} to PATH.")
    actual = subprocess.check_output(
        [candidate, "-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))"], text=True,
    ).strip()
    if actual != version:
        raise CheckFailure(f"{candidate} reports Python {actual}, expected {version}.")
    return candidate


def check_metadata(root):
    version = (root / "mcp-wrapper-version").read_text().strip()
    if json.loads((root / "mcp-manifest.json").read_text())["version"] != version:
        raise CheckFailure("Manifest version disagrees with mcp-wrapper-version.")
    if f"KUSTO_QUERY_CLI_VERSION={version}" not in (root / ".env").read_text().splitlines():
        raise CheckFailure("Default Docker version disagrees with mcp-wrapper-version.")
    for path in (root / "examples").glob("*.json"):
        data = json.loads(path.read_text())
        actual = data.get("metadata", {}).get("wrapper_version")
        if actual is not None and actual != version:
            raise CheckFailure(f"Stale release version in {path.name}.")
    if f"## {version}\n" not in (root / "CHANGELOG.md").read_text():
        raise CheckFailure(f"CHANGELOG.md needs a section for {version}.")
    return version


def check_python(runner, row, interpreter):
    version = row["python"]
    with tempfile.TemporaryDirectory(prefix=f"kqc-python-{version}-") as directory:
        base = Path(directory)
        runtime = base / "runtime/bin/python"
        legacy = base / "legacy/bin/python"
        runner.run(f"python-{version}-venv", [interpreter, "-m", "venv", str(base / "runtime")])
        runner.run(f"python-{version}-install", [runtime, "-m", "pip", "install", "-r", "requirements.txt", row["mcp"]])
        runner.run(f"python-{version}-dependencies", [runtime, "-m", "pip", "check"])
        runner.run(f"python-{version}-resolved", [runtime, "-m", "pip", "freeze"])
        runner.run(f"python-{version}-tests", [runtime, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
        for entrypoint in ("k2json.py", "k2csv.py"):
            runner.run(f"python-{version}-{entrypoint}-help", [runtime, entrypoint, "--help"], timeout=60)
        runner.run(f"python-{version}-stdio", [runtime, "tests/integration/mcp_smoke.py"], timeout=180)
        runner.run(f"python-{version}-legacy-venv", [interpreter, "-m", "venv", str(base / "legacy")])
        runner.run(f"python-{version}-legacy-install", [legacy, "-m", "pip", "install", row["legacy"]])
        runner.run(f"python-{version}-legacy-resolved", [legacy, "-m", "pip", "freeze"])
        runner.run(f"python-{version}-legacy-stdio", [legacy, "tests/integration/mcp_smoke.py", runtime, "mcp-stdio-server.py"], timeout=180)


def check_docker(runner, platform, interpreter, existing_image=None):
    architecture = platform.split("/")[-1]
    # Unique tags avoid overwriting a developer's existing runtime images.
    tag = f"kusto-query-cli:release-check-{architecture}-{os.getpid()}"
    if existing_image:
        tag = existing_image
        runner.run(f"docker-{architecture}-pull", ["docker", "pull", "--platform", platform, tag])
    else:
        runner.run(f"docker-{architecture}-build", [
            "docker", "buildx", "build", "--pull", "--load", "--platform", platform, "-t", tag, ".",
        ])
    image = json.loads(runner.run(f"docker-{architecture}-inspect", ["docker", "image", "inspect", tag]))[0]
    if f"{image['Os']}/{image['Architecture']}" != platform:
        raise CheckFailure(f"Built image architecture does not match {platform}.")
    # All tests below use the immutable local image ID, not a moving tag.
    image_id = image["Id"]
    command = ["docker", "run", "--rm", "--platform", platform, image_id]
    runner.run(f"docker-{architecture}-azure", [*command, "az", "version"])
    runner.run(f"docker-{architecture}-dependencies", [*command, "python", "-m", "pip", "check"])
    runner.run(f"docker-{architecture}-resolved", [*command, "python", "-m", "pip", "freeze"])
    for entrypoint in ("k2json.py", "k2csv.py"):
        runner.run(f"docker-{architecture}-{entrypoint}-help", [*command, "python", entrypoint, "--help"], timeout=60)
    # Exercise the actual one-shot launcher without login or cloud requests.
    runner.run(f"docker-{architecture}-wrapper", [*command, "python", "-c", (
        "import json, pathlib, subprocess, sys; "
        "result = subprocess.run([sys.executable, 'mcp-wrapper.py'], input='{}', "
        "text=True, capture_output=True, check=True); "
        "data = json.loads(result.stdout); "
        "assert data['error']['code'] == 'UNKNOWN_ACTION', data; "
        "assert data['metadata']['wrapper_version'] == pathlib.Path('mcp-wrapper-version').read_text().strip(); "
        "print('One-shot wrapper: passed')"
    )], timeout=60)
    with tempfile.TemporaryDirectory(prefix="kqc-docker-client-") as directory:
        client = Path(directory) / "bin/python"
        runner.run(f"docker-{architecture}-client-venv", [interpreter, "-m", "venv", directory])
        runner.run(f"docker-{architecture}-client-install", [client, "-m", "pip", "install", "mcp>=2.2.0,<3"])
        server = ["docker", "run", "--rm", "-i", "--platform", platform, "-e", "MCP_LOG_LEVEL=CRITICAL", image_id, "python", "mcp-stdio-server.py"]
        runner.run(f"docker-{architecture}-stdio", [client, "tests/integration/mcp_smoke.py", *server], timeout=300)
        runner.run(f"docker-{architecture}-legacy-install", [client, "-m", "pip", "install", "mcp==1.26.0"])
        runner.run(f"docker-{architecture}-legacy-stdio", [client, "tests/integration/mcp_smoke.py", *server], timeout=180)
    return {"platform": platform, "local_tag": tag, "image_id": image_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["matrix", "metadata", "python", "docker"])
    parser.add_argument("--python-version")
    parser.add_argument("--platform")
    parser.add_argument("--image", help="Validate an existing registry image instead of building")
    parser.add_argument("--output", type=Path, default=ROOT / ".release/ci-checks")
    args = parser.parse_args()
    config = matrix()
    if args.suite == "matrix":
        print(json.dumps(config))
        return
    check_metadata(ROOT)
    if args.suite == "metadata":
        return
    runner = Runner(ROOT, args.output.resolve())
    if args.suite == "python":
        row = next((row for row in config["python"] if row["python"] == args.python_version), None)
        if row is None:
            parser.error("--python-version must name a configured matrix entry")
        check_python(runner, row, find_python(row["python"]))
    else:
        if args.platform not in [row["platform"] for row in config["docker"]]:
            parser.error("--platform must name a configured matrix entry")
        image = check_docker(runner, args.platform, find_python(config["python"][0]["python"]), args.image)
        write_json(runner.output / "image.json", image)


if __name__ == "__main__":
    try:
        main()
    except (CheckFailure, subprocess.SubprocessError, OSError) as exc:
        print(f"Release checks failed: {exc}", file=sys.stderr)
        sys.exit(1)
