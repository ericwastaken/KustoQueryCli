import contextlib
import fcntl
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import release
from release_checks import CheckFailure, check_metadata


class VersionTests(unittest.TestCase):


    def test_versions_and_release_candidates(self):
        for bad in ("1.2", "1.02.3", "1.2.3-rc.0", "1.2.3+build", "1.2.3;echo bad"):
            with self.subTest(bad=bad), self.assertRaises(CheckFailure):
                release.Version(bad)
        self.assertLess(release.Version("1.2.3-rc.2"), release.Version("1.2.3-rc.10"))
        self.assertLess(release.Version("1.2.3-rc.10"), release.Version("1.2.3"))
        self.assertEqual(str(release.Version("v1.2.3")), "1.2.3")


    def test_recommendations(self):
        current = release.Version("1.3.0")
        for message, expected in [
            ("fix: compatibility", "1.3.1"),
            ("feat(release): add script", "1.4.0"),
            ("feat!: remove API", "2.0.0"),
            ("refactor\n\nBREAKING CHANGE: removes API", "2.0.0"),
        ]:
            self.assertEqual(str(release.recommend(current, [current], message)[0]), expected)
        self.assertEqual(release.recommend(current, [], "feat: new")[0], current)


class RegistryTests(unittest.TestCase):


    def check(self, code, stderr, tags="", releases=None):
        response = subprocess.CompletedProcess([], code, stdout="", stderr=stderr)
        with patch.object(release, "git", return_value=tags), patch.object(release, "command", return_value=response):
            return release.check_conflicts(Path("."), "Owner/Repo", release.Version("1.4.0"), releases or [])


    def test_existing_tag_release_and_image_are_conflicts(self):
        for code, tags, releases in [(1, "v1.4.0", []), (1, "", [{"tag_name": "v1.4.0", "draft": True}]), (0, "", [])]:
            with self.subTest(code=code, tags=tags), self.assertRaisesRegex(CheckFailure, "Version conflict"):
                self.check(code, "", tags, releases)


    def test_only_explicit_missing_manifest_means_available(self):
        image = self.check(1, "ERROR: ghcr.io/owner/repo:1.4.0: not found")
        self.assertEqual(image, "ghcr.io/owner/repo:1.4.0")
        self.check(1, "ERROR: manifest unknown")


    def test_auth_and_network_errors_are_not_absence(self):
        for error in ("403 Forbidden", "401 Unauthorized", "dial: host not found", "connection timeout", "failed to authorize: manifest unknown"):
            with self.subTest(error=error), self.assertRaisesRegex(CheckFailure, "incomplete"):
                self.check(1, error)


class PreparationTests(unittest.TestCase):


    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.directory) / "repo"
        self.root.mkdir()
        self.remote = Path(self.directory) / "origin.git"
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.name", "Release Tests")
        self.run_git("config", "user.email", "release-tests@example.invalid")
        files = {
            "mcp-wrapper-version": "1.3.0\n",
            "mcp-manifest.json": '{"version": "1.3.0"}\n',
            ".env": "KUSTO_QUERY_CLI_VERSION=1.3.0\n",
            ".gitignore": "/.release/\n",
            ".dockerignore": "*\n!lib/\n!mcp-wrapper-version\n",
            "README-MCP-WRAPPER.md": 'Example: "wrapper_version": "1.3.0"\n',
            "README-MCP-SERVER.md": "docker run kusto-query-cli:1.3.0\n",
            "CHANGELOG.md": "# Changelog\n\n## 1.3.0\n\n- Existing release.\n",
            "examples/QUERY.success.json": '{"metadata": {"wrapper_version": "1.3.0"}}\n',
            "scripts/release-matrix.json": (SCRIPTS / "release-matrix.json").read_text(),
        }
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        self.run_git("add", ".")
        self.run_git("commit", "-m", "Initial release")
        self.run_git("tag", "v1.3.0")
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        self.run_git("remote", "add", "origin", str(self.remote))
        self.run_git("push", "origin", "main", "--tags")
        self.run_git("switch", "-c", "codex/release-test")
        self.real_command = release.command
        self.enterContext(patch.object(release, "command", side_effect=self.fake_command))
        self.enterContext(patch.object(release, "repository", return_value={"full_name": "owner/repo", "default_branch": "main"}))
        self.enterContext(patch.object(release, "api", return_value=[[]]))
        self.conflicts = self.enterContext(patch.object(release, "check_conflicts", return_value="ghcr.io/owner/repo:1.3.1"))
        self.enterContext(patch.object(release, "find_python", return_value=sys.executable))
        self.enterContext(patch.object(release.shutil, "which", return_value="/usr/bin/tool"))
        self.python_checks = self.enterContext(patch.object(release, "check_python"))
        self.docker_checks = self.enterContext(patch.object(release, "check_docker", return_value={"image_id": "sha256:test"}))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))


    def run_git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True).strip()


    def fake_command(self, args, root=release.ROOT, allowed=(0,)):
        if args[0] in ("gh", "docker"):
            return subprocess.CompletedProcess(args, 0, "", "")
        return self.real_command(args, root, allowed)


    def prepare(self, *extra):
        return release.main(["--version", "1.3.1", "--non-interactive", *extra], self.root)


    def latest_report(self):
        files = sorted((self.root / ".release/runs").glob("*/report.json"), key=lambda path: path.stat().st_mtime_ns)
        return json.loads(files[-1].read_text())


    def test_complete_flow_updates_all_metadata_without_publishing(self):
        head = self.run_git("rev-parse", "HEAD")
        self.assertEqual(self.prepare(), 0)
        self.assertEqual(check_metadata(self.root), "1.3.1")
        self.assertEqual(self.latest_report()["status"], "passed")
        self.assertEqual(self.run_git("rev-parse", "HEAD"), head)
        self.assertEqual(self.run_git("tag", "--list"), "v1.3.0")
        self.assertEqual(self.python_checks.call_count, 2)
        self.assertEqual(self.docker_checks.call_count, 2)
        self.assertEqual(self.conflicts.call_count, 2)
        self.assertEqual(json.loads((self.root / "examples/QUERY.success.json").read_text())["metadata"]["wrapper_version"], "1.3.1")


    def test_failure_preserves_edits_and_rerun_resumes(self):
        self.docker_checks.side_effect = CheckFailure("Docker failed")
        self.assertEqual(self.prepare(), 1)
        self.assertEqual(self.latest_report()["status"], "incomplete")
        self.assertEqual(check_metadata(self.root), "1.3.1")
        notes = self.root / "CHANGELOG.md"
        notes.write_text(notes.read_text().replace("Review and describe the changes included in this release.", "Reviewed release notes."))
        self.docker_checks.side_effect = None
        self.assertEqual(self.prepare(), 0)
        self.assertIn("Reviewed release notes.", notes.read_text())
        self.assertEqual(notes.read_text().count("## 1.3.1\n"), 1)


    def test_conflict_recheck_catches_a_release_created_during_validation(self):
        self.conflicts.side_effect = ["image", CheckFailure("Version conflict at final check")]
        self.assertEqual(self.prepare(), 1)
        self.assertEqual(self.latest_report()["status"], "incomplete")


    def test_check_only_does_not_edit_tracked_files(self):
        self.assertEqual(self.prepare(), 0)
        before = self.run_git("diff")
        self.assertEqual(self.prepare("--check-only"), 0)
        self.assertEqual(before, self.run_git("diff"))


    def test_dirty_source_and_untracked_runtime_files_are_rejected(self):
        notes = self.root / "CHANGELOG.md"
        notes.write_text(notes.read_text() + "User edits\n")
        self.assertEqual(self.prepare(), 1)
        self.assertIn("Commit or stash", self.latest_report()["error"])
        self.run_git("restore", "CHANGELOG.md")
        (self.root / "lib").mkdir()
        (self.root / "lib/untracked.py").write_text("print('not tracked')\n")
        self.assertEqual(self.prepare(), 1)
        self.assertIn("untracked release inputs", self.latest_report()["error"])


    def test_interruption_is_reported_and_can_resume(self):
        self.python_checks.side_effect = KeyboardInterrupt
        self.assertEqual(self.prepare(), 1)
        self.assertEqual(self.latest_report()["status"], "incomplete")
        self.python_checks.side_effect = None
        self.assertEqual(self.prepare(), 0)


    def test_source_mutation_during_checks_prevents_success(self):
        self.python_checks.side_effect = lambda *args: (self.root / "README-MCP-SERVER.md").write_text("changed during checks\n")
        self.assertEqual(self.prepare(), 1)
        self.assertIn("Source changed", self.latest_report()["error"])


    def test_cancel_does_not_edit(self):
        with patch("builtins.input", return_value="n"):
            self.assertEqual(release.main(["--version", "1.3.1"], self.root), 1)
        self.assertEqual(self.run_git("diff"), "")


    def test_maintenance_release_does_not_become_latest(self):
        self.enterContext(patch.object(release, "api", return_value=[[{"tag_name": "v2.0.0"}]]))
        self.assertEqual(self.prepare(), 0)
        self.assertFalse(self.latest_report()["eligible_for_latest"])


    def test_partial_metadata_write_can_resume(self):
        changes = release.prepare_files(self.root, release.Version("1.3.1"), "fix: example")
        real_replace = Path.replace


        def interrupted_replace(path, target):
            if target == self.root / "mcp-manifest.json":
                raise KeyboardInterrupt
            return real_replace(path, target)

        with patch.object(Path, "replace", interrupted_replace), self.assertRaises(KeyboardInterrupt):
            release.apply_preparation(self.root, release.Version("1.3.1"), changes, None)
        self.assertEqual(self.prepare(), 0)
        self.assertEqual(check_metadata(self.root), "1.3.1")


    def test_concurrent_preparation_is_rejected(self):
        (self.root / ".release").mkdir()
        with (self.root / ".release/preparation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.prepare(), 1)
        self.assertIn("Another release preparation", self.latest_report()["error"])


if __name__ == "__main__":
    unittest.main()
