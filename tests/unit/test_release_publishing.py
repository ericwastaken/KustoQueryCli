import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import publish_release as publisher
from release import Version
from release_checks import CheckFailure


class PublishingTests(unittest.TestCase):


    def test_maintenance_and_candidates_do_not_replace_latest(self):
        releases = [{"tag_name": "v2.0.0"}, {"tag_name": "v1.2.4"}]
        self.assertEqual(publisher.aliases(Version("1.2.5"), releases), ["1.2"])
        self.assertEqual(publisher.aliases(Version("1.2.3"), releases), [])
        self.assertEqual(publisher.aliases(Version("3.0.0-rc.1"), releases), [])
        self.assertEqual(publisher.aliases(Version("2.0.0"), releases), ["2.0", "latest"])
        self.assertEqual(publisher.aliases(Version("3.0.0"), releases), ["3.0", "latest"])


    def test_drafts_and_prereleases_do_not_block_stable_alias(self):
        releases = [{"tag_name": "v9.0.0", "draft": True},
                    {"tag_name": "v8.0.0-rc.1", "prerelease": True}, {"tag_name": "unrelated"}]
        self.assertEqual(publisher.aliases(Version("2.0.0"), releases), ["2.0", "latest"])


    def test_wrong_missing_or_extra_architecture_is_rejected(self):
        reports = [{"platform": "linux/amd64", "digest": "sha256:a"},
                   {"platform": "linux/arm64", "digest": "sha256:b"}]
        descriptors = [{"platform": {"os": "linux", "architecture": row["platform"].split("/")[1]},
                        "digest": row["digest"]} for row in reports]
        publisher.verify_index({"manifests": descriptors}, reports)
        for bad in (descriptors[:1], descriptors + descriptors[:1],
                    [dict(descriptors[0], digest="sha256:different"), descriptors[1]]):
            with self.assertRaises(CheckFailure):
                publisher.verify_index({"manifests": bad}, reports)


    def test_reports_must_match_release_and_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = []
            for architecture in ("amd64", "arm64"):
                target = root / architecture
                target.mkdir()
                report = {"platform": f"linux/{architecture}", "version": "2.0.0",
                          "commit": "correct", "status": "passed", "digest": "sha256:" + "a" * 64}
                (target / "image-report.json").write_text(json.dumps(report))
                reports.append(report)
            self.assertEqual(len(publisher.collect_reports(root, Version("2.0.0"), "correct")), 2)
            with self.assertRaises(CheckFailure):
                publisher.collect_reports(root, Version("2.0.0"), "wrong")
            with self.assertRaises(CheckFailure):
                publisher.collect_reports(root, Version("2.0.1"), "correct")
            (root / "arm64/image-report.json").unlink()
            with self.assertRaises(CheckFailure):
                publisher.collect_reports(root, Version("2.0.0"), "correct")


    def test_existing_candidate_must_have_expected_revision_and_version(self):
        image = {"Config": {"Labels": {"org.opencontainers.image.revision": "correct",
                                        "org.opencontainers.image.version": "2.0.0"}}}
        publisher.verify_labels(image, Version("2.0.0"), "correct")
        with self.assertRaises(CheckFailure):
            publisher.verify_labels(image, Version("2.0.0"), "wrong")
        with self.assertRaises(CheckFailure):
            publisher.verify_labels(image, Version("2.0.1"), "correct")


    def test_registry_permission_errors_cannot_be_treated_as_available(self):
        token = json.dumps({"token": "test-token"}).encode()
        for code in (401, 403, 500):
            failure = HTTPError("https://ghcr.io", code, "failure", {}, None)
            with patch.object(publisher, "request", side_effect=[token, failure]):
                with self.assertRaises(HTTPError):
                    publisher.registry_manifest("owner/repo", "2.0.0", anonymous=True)
        absent = HTTPError("https://ghcr.io", 404, "not found", {}, None)
        with patch.object(publisher, "request", side_effect=[token, absent]):
            self.assertIsNone(publisher.registry_manifest("owner/repo", "2.0.0", anonymous=True))
        # A token-endpoint 404 also does not prove a version is unused.
        with patch.object(publisher, "request", side_effect=absent):
            with self.assertRaises(HTTPError):
                publisher.registry_manifest("owner/repo", "2.0.0", anonymous=True)


if __name__ == "__main__":
    unittest.main()
