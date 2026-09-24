"""Tag-triggered GHCR and GitHub publisher; local preparation never calls this."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from release import Version, api, command, git
from release_checks import CheckFailure, ROOT, Runner, check_docker, check_metadata, find_python, matrix, write_json


MEDIA_TYPES = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))


def request(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=60) as response:
        return response.read()


def registry_manifest(repository, reference, anonymous=False):
    """Only an explicit manifest 404 means absent; auth/network failures stop work."""
    headers = {}
    if not anonymous:
        credential = f"{os.environ['GITHUB_ACTOR']}:{os.environ['GH_TOKEN']}"
        headers["Authorization"] = "Basic " + base64.b64encode(credential.encode()).decode()
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
    token = json.loads(request(f"https://ghcr.io/token?{query}", headers))["token"]
    try:
        raw = request(f"https://ghcr.io/v2/{repository}/manifests/{reference}", {
            "Authorization": f"Bearer {token}", "Accept": MEDIA_TYPES,
        })
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return {"digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "manifest": json.loads(raw)}


def context(tag):
    version = Version(tag)
    if tag != f"v{version}" or check_metadata(ROOT) != str(version):
        raise CheckFailure("Release tag must be v<canonical application version>.")
    repository = os.environ["GITHUB_REPOSITORY"]
    commit = git("rev-parse", "HEAD")
    if git("rev-parse", f"{tag}^{{commit}}") != commit:
        raise CheckFailure("Checkout does not match the immutable release tag.")
    git("fetch", "origin", "+refs/heads/*:refs/remotes/origin/*")
    branches = git("branch", "-r", "--contains", commit).splitlines()
    allowed = [line.strip() for line in branches if re.fullmatch(
        r"origin/(main|maintenance/\d+\.\d+)", line.strip(),
    )]
    if not allowed:
        raise CheckFailure("Release commit must already be merged into main or maintenance/X.Y.")
    return version, repository, commit


def prepare(tag):
    version, repository, commit = context(tag)
    values = {"version": str(version), "commit": commit, "image": f"ghcr.io/{repository.lower()}"}
    values.update({name: json.dumps({"include": rows}) for name, rows in matrix().items()})
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for key, value in values.items():
            print(f"{key}={value}", file=output)


def verify_labels(image, version, commit):
    labels = image.get("Config", {}).get("Labels") or {}
    if labels.get("org.opencontainers.image.revision") != commit or labels.get("org.opencontainers.image.version") != str(version):
        raise CheckFailure("Existing candidate image belongs to different source/version.")


def publish_image(tag, platform, output):
    version, repository, commit = context(tag)
    if platform not in [row["platform"] for row in matrix()["docker"]]:
        raise CheckFailure("Platform is outside the shared release matrix.")
    architecture = platform.split("/")[-1]
    package = repository.lower()
    image = f"ghcr.io/{package}"
    candidate = f"build-{commit}-{architecture}"
    runner = Runner(ROOT, output)
    existing = registry_manifest(package, candidate)
    if existing is None:
        runner.run("build", [
            "docker", "buildx", "build", "--pull", "--load", "--provenance=false",
            "--platform", platform, "--tag", f"{image}:{candidate}",
            "--label", f"org.opencontainers.image.source=https://github.com/{repository}",
            "--label", f"org.opencontainers.image.revision={commit}",
            "--label", f"org.opencontainers.image.version={version}", ".",
        ])
        runner.run("push-candidate", ["docker", "push", f"{image}:{candidate}"])
        existing = registry_manifest(package, candidate)
    if existing is None:
        raise CheckFailure("Candidate push did not produce a manifest.")
    reference = f"{image}@{existing['digest']}"
    result = check_docker(runner, platform, find_python("3.12"), reference)
    inspected = json.loads(command(["docker", "image", "inspect", result["image_id"]]).stdout)[0]
    verify_labels(inspected, version, commit)
    actual = command(["docker", "run", "--rm", "--platform", platform,
                      result["image_id"], "cat", "mcp-wrapper-version"]).stdout.strip()
    if actual != str(version):
        raise CheckFailure("Image runtime version disagrees with release tag.")
    write_json(output / "image-report.json", {
        "version": str(version), "commit": commit, "platform": platform,
        "digest": existing["digest"], "image_id": result["image_id"], "status": "passed",
        "dependencies": next(output.glob("*-resolved.log")).read_text().splitlines(),
    })


def collect_reports(directory, version, commit):
    reports = [json.loads(path.read_text()) for path in sorted(directory.glob("**/image-report.json"))]
    platforms = [row["platform"] for row in matrix()["docker"]]
    if sorted(item["platform"] for item in reports) != sorted(platforms):
        raise CheckFailure("Exactly one passing report is required for every architecture.")
    for item in reports:
        if (item["status"] != "passed" or item["version"] != str(version)
                or item["commit"] != commit or not re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"])):
            raise CheckFailure("Image report does not match this release.")
    return reports


def verify_index(manifest, reports):
    descriptors = manifest.get("manifests", [])
    actual = {(item["platform"]["os"] + "/" + item["platform"]["architecture"], item["digest"])
              for item in descriptors}
    expected = {(item["platform"], item["digest"]) for item in reports}
    if actual != expected or len(descriptors) != len(expected):
        raise CheckFailure("Version image conflicts with the tested architecture digests.")


def aliases(version, releases):
    if version.rc is not None:
        return []
    stable = []
    for item in releases:
        if item.get("draft") or item.get("prerelease"):
            continue
        try:
            parsed = Version(item["tag_name"])
        except CheckFailure:
            continue
        if parsed.rc is None:
            stable.append(parsed)
    result = []
    if not any(item.core[:2] == version.core[:2] and item > version for item in stable):
        result.append(".".join(map(str, version.core[:2])))
    if not any(item > version for item in stable):
        result.append("latest")
    return result


def release_notes(version, repository, commit, digest):
    changelog = (ROOT / "CHANGELOG.md").read_text()
    section = changelog.split(f"## {version}\n", 1)[1].split("\n## ", 1)[0].strip()
    image = f"ghcr.io/{repository.lower()}"
    return (f"{section}\n\nContainer: `{image}:{version}` (Linux AMD64 and ARM64).\n\n"
            f"Immutable image: `{image}@{digest}`\n\n"
            f"Source commit: `{commit}`. See `release-manifest.json` for tested architecture "
            "digests, resolved dependencies, and the build run.\n")


def finish(tag, directory):
    version, repository, commit = context(tag)
    package = repository.lower()
    image = f"ghcr.io/{package}"
    reports = collect_reports(directory, version, commit)
    existing = registry_manifest(package, str(version))
    if existing is None:
        command(["docker", "buildx", "imagetools", "create", "--tag", f"{image}:{version}",
                 *[f"{image}@{item['digest']}" for item in reports]])
        existing = registry_manifest(package, str(version))
    if existing is None:
        raise CheckFailure("Published version manifest is missing.")
    verify_index(existing["manifest"], reports)
    # Fail before announcing a release if consumers cannot pull without credentials.
    try:
        public = registry_manifest(package, str(version), anonymous=True)
    except HTTPError as exc:
        raise CheckFailure("Image is not publicly readable. Set the GHCR package visibility to public, then rerun failed jobs.") from exc
    if public is None or public["digest"] != existing["digest"]:
        raise CheckFailure("Anonymous manifest does not match the tested release.")
    releases = [item for page in api(f"repos/{repository}/releases?per_page=100") for item in page]
    current = next((item for item in releases if item["tag_name"] == tag), None)
    manifest = {
        "version": str(version), "commit": commit, "image": image, "digest": existing["digest"],
        "platforms": reports,
        "workflow": f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
    }
    with tempfile.TemporaryDirectory(prefix="kqc-publish-") as temporary:
        base = Path(temporary)
        asset = base / "release-manifest.json"
        notes = base / "notes.md"
        write_json(asset, manifest)
        notes.write_text(release_notes(version, repository, commit, existing["digest"]))
        if current and not current["draft"]:
            downloaded = base / "published"
            downloaded.mkdir()
            command(["gh", "release", "download", tag, "--repo", repository,
                     "--pattern", asset.name, "--dir", str(downloaded)])
            previous = json.loads((downloaded / asset.name).read_text())
            if any(previous.get(key) != manifest[key] for key in ("version", "commit", "image", "digest")):
                raise CheckFailure("Published GitHub release conflicts with this image/source.")
        else:
            if current is None:
                command(["gh", "release", "create", tag, "--repo", repository, "--verify-tag", "--draft",
                         "--title", tag, "--notes-file", str(notes),
                         *(["--prerelease"] if version.rc else [])])
            command(["gh", "release", "upload", tag, str(asset), "--repo", repository, "--clobber"])
            command(["gh", "release", "edit", tag, "--repo", repository, "--notes-file", str(notes),
                     "--prerelease=" + str(version.rc is not None).lower()])
        selected = aliases(version, releases)
        for alias in selected:
            command(["docker", "buildx", "imagetools", "create", "--tag", f"{image}:{alias}",
                     f"{image}@{existing['digest']}"])
            if registry_manifest(package, alias)["digest"] != existing["digest"]:
                raise CheckFailure(f"Alias {alias} failed verification.")
        if not current or current["draft"]:
            command(["gh", "release", "edit", tag, "--repo", repository, "--draft=false",
                     "--latest=" + str("latest" in selected).lower()])
    print(f"Published https://github.com/{repository}/releases/tag/{tag}")
    print(f"Image: {image}:{version}@{existing['digest']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "image", "finish"])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--platform")
    parser.add_argument("--output", type=Path, default=ROOT / ".release/publish")
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare(args.tag)
    elif args.stage == "image":
        publish_image(args.tag, args.platform, args.output)
    else:
        finish(args.tag, args.output)


if __name__ == "__main__":
    try:
        main()
    except (CheckFailure, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"Release publication stopped: {exc}", file=sys.stderr)
        sys.exit(1)
