import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import maintain_releases as maintenance
from release_checks import CheckFailure


class MaintenanceTests(unittest.TestCase):


    def test_replacement_accepts_original_and_partial_retry_only(self):
        original = {"commit": maintenance.ORIGINAL_V2, "digest": maintenance.ORIGINAL_DIGEST}
        updated = {"commit": "new-commit", "digest": "sha256:new"}
        for previous in (original, updated):
            for digest in (maintenance.ORIGINAL_DIGEST, "sha256:new"):
                maintenance.guard_replacement(previous, {"digest": digest}, "new-commit", "sha256:new")
        for previous, current in (
            ({**original, "commit": "unexpected"}, {"digest": maintenance.ORIGINAL_DIGEST}),
            (original, {"digest": "sha256:unexpected"}), (original, None),
            (updated, {"digest": "sha256:other-replacement"}),
        ):
            with self.assertRaises(CheckFailure):
                maintenance.guard_replacement(previous, current, "new-commit", "sha256:new")


    def test_historical_source_and_tag_must_match_original(self):
        tag = "v1.2.1"
        correct = maintenance.HISTORICAL[tag]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mcp-wrapper-version").write_text("1.2.1\n")
            for head, tagged in ((correct, correct), ("wrong", correct), (correct, "moved")):
                with (
                    patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}),
                    patch.object(maintenance, "command", side_effect=[SimpleNamespace(stdout=head), SimpleNamespace(stdout=tagged)]),
                ):
                    if head == tagged == correct:
                        self.assertEqual(maintenance.source_context(tag, root)[2], correct)
                    else:
                        with self.assertRaises(CheckFailure):
                            maintenance.source_context(tag, root)


    def test_v2_replacement_requires_workflow_commit_and_allowed_old_tag(self):
        for head, tagged, workflow in (("new", "unexpected", "new"), ("new", maintenance.ORIGINAL_V2, "other")):
            with (
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_SHA": workflow}),
                patch.object(maintenance, "check_metadata", return_value="2.0.0"),
                patch.object(maintenance, "command", side_effect=[SimpleNamespace(stdout=head), SimpleNamespace(stdout=tagged)]),
            ):
                with self.assertRaises(CheckFailure):
                    maintenance.source_context("v2.0.0", Path("/unused"))
