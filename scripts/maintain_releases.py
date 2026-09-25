"""Narrow, manual publication for the approved v2 layout and 1.x backfills.

Normal releases continue to use publish_release.py and immutable version tags.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from publish_release import (
    aliases, collect_reports, registry_manifest, release_notes, verify_index, verify_labels,
)
from release import Version, api, command
from release_checks import CheckFailure, ROOT, Runner, check_docker, check_metadata, find_python, write_json


ORIGINAL_V2 = "d2ca0199b214601f175838ce8dcdff358c036dd2"
ORIGINAL_DIGEST = "sha256:f943c0060092bdaad8b64eb7e476eb5aaf820b974fcd6b92bd552468ff68675d"
HISTORICAL = {
    "v1.2.1": "0b5817b1cdcc834e6d174a51dffd3fdf04549960",
    "v1.3.0": "6dac2d013a61861e87c722044c42ac0f842973d3",
}


def source_context(tag, source):
    version = Version(tag)
    repository = os.environ["GITHUB_REPOSITORY"]
    commit = command(["git", "rev-parse", "HEAD"], root=source).stdout.strip()
    tag_commit = command(["git", "rev-parse", f"{tag}^{{commit}}"], root=source).stdout.strip()
    if tag in HISTORICAL:
        if commit != HISTORICAL[tag] or tag_commit != commit:
            raise CheckFailure("Historical builds must use the original, unchanged source tag.")
        if (source / "mcp-wrapper-version").read_text().strip() != str(version):
            raise CheckFailure("Historical runtime version does not match its tag.")
    elif tag == "v2.0.0":
        if check_metadata(source) != str(version) or tag_commit not in (ORIGINAL_V2, commit):
            raise CheckFailure("Only the approved original v2 release may be replaced.")
        # The workflow is dispatched from main and checks out its immutable SHA twice.
        if commit != os.environ["GITHUB_SHA"]:
            raise CheckFailure("Replacement source must be the workflow's tested main commit.")
        command(["git", "merge-base", "--is-ancestor", commit, "origin/main"], root=source)
        command(["git", "merge-base", "--is-ancestor", ORIGINAL_V2, commit], root=source)
    else:
        raise CheckFailure("This maintenance workflow is limited to v1.2.1, v1.3.0 and v2.0.0.")
    return version, repository, commit


def historical_checks(runner, image, platform, version):
    runner.run("pull", ["docker", "pull", "--platform", platform, image])
    inspected = json.loads(runner.run("inspect", ["docker", "image", "inspect", image]))[0]
    if f"{inspected['Os']}/{inspected['Architecture']}" != platform:
        raise CheckFailure("Historical image architecture mismatch.")
    image_id = inspected["Id"]
    run = ["docker", "run", "--rm", "--platform", platform, image_id]
    runner.run("azure", [*run, "az", "version"])
    runner.run("dependencies", [*run, "python", "-m", "pip", "check"])
    runner.run("resolved", [*run, "python", "-m", "pip", "freeze"])
    major = 1 if str(version) == "1.2.1" else 2
    runner.run("runtime-version", [*run, "python", "-c", (
        "from pathlib import Path; from importlib.metadata import version; "
        f"assert Path('mcp-wrapper-version').read_text().strip() == {str(version)!r}; "
        f"assert int(version('mcp').split('.')[0]) == {major}"
    )])
    for entrypoint in ("k2json.py", "k2csv.py"):
        runner.run(entrypoint, [*run, "python", entrypoint, "--help"], timeout=60)
    runner.run("wrapper", [*run, "python", "-c", (
        "import json, subprocess; r = subprocess.run(['python', 'mcp-wrapper.py'], "
        "input='{}', text=True, capture_output=True, check=True); d = json.loads(r.stdout); "
        "assert d['error']['code'] == 'UNKNOWN_ACTION', d; "
        f"assert d['metadata']['wrapper_version'] == {str(version)!r}"
    )], timeout=60)
    with tempfile.TemporaryDirectory(prefix="kqc-historical-client-") as temporary:
        client = Path(temporary) / "bin/python"
        runner.run("client-venv", [find_python("3.12"), "-m", "venv", temporary])
        for sdk in ("mcp==1.26.0", "mcp>=2.2.0,<3"):
            runner.run("client-install", [client, "-m", "pip", "install", sdk])
            runner.run("stdio", [client, str(ROOT / "tests/integration/historical_smoke.py"), str(version),
                                "docker", "run", "--rm", "-i", "--platform", platform,
                                "-e", "MCP_LOG_LEVEL=CRITICAL", image_id, "python", "mcp-stdio-server.py"], timeout=240)
    return inspected


def image_stage(tag, source, platform, output):
    version, repository, commit = source_context(tag, source)
    if platform not in ("linux/amd64", "linux/arm64"):
        raise CheckFailure("Unsupported image platform.")
    package = repository.lower()
    image = f"ghcr.io/{package}"
    candidate = f"build-{commit}-{platform.split('/')[-1]}"
    runner = Runner(source, output)
    existing = registry_manifest(package, candidate)
    if existing is None:
        dockerfile = "docker/Dockerfile" if tag == "v2.0.0" else "Dockerfile"
        runner.run("build", ["docker", "buildx", "build", "--pull", "--load", "--provenance=false",
                             "--platform", platform, "--file", dockerfile, "--tag", f"{image}:{candidate}",
                             "--label", f"org.opencontainers.image.source=https://github.com/{repository}",
                             "--label", f"org.opencontainers.image.revision={commit}",
                             "--label", f"org.opencontainers.image.version={version}", "."])
        runner.run("push", ["docker", "push", f"{image}:{candidate}"])
        existing = registry_manifest(package, candidate)
    if existing is None:
        raise CheckFailure("Candidate image is missing after upload.")
    reference = f"{image}@{existing['digest']}"
    if tag == "v2.0.0":
        # Source and tooling are the same commit; use the normal release gates.
        result = check_docker(runner, platform, find_python("3.12"), reference)
        inspected = json.loads(command(["docker", "image", "inspect", result["image_id"]]).stdout)[0]
    else:
        inspected = historical_checks(runner, reference, platform, version)
    verify_labels(inspected, version, commit)
    write_json(output / "image-report.json", {
        "version": str(version), "commit": commit, "platform": platform,
        "digest": existing["digest"], "image_id": inspected["Id"], "status": "passed",
        "dependencies": next(output.glob("*-resolved.log")).read_text().splitlines(),
    })


def guard_replacement(previous, current, commit, desired_digest):
    """Allow only the known original or this exact tested replacement, including retries."""
    if (previous.get("commit"), previous.get("digest")) not in (
        (ORIGINAL_V2, ORIGINAL_DIGEST), (commit, desired_digest),
    ):
        raise CheckFailure("Existing release manifest is neither the original nor this replacement.")
    if current is None or current["digest"] not in (ORIGINAL_DIGEST, desired_digest):
        raise CheckFailure("Existing v2 image has changed unexpectedly.")


def finish_stage(tag, source, output):
    version, repository, commit = source_context(tag, source)
    package = repository.lower()
    image = f"ghcr.io/{package}"
    reports = collect_reports(output, version, commit)
    releases = [item for page in api(f"repos/{repository}/releases?per_page=100") for item in page]
    current_release = next(item for item in releases if item["tag_name"] == tag)
    if current_release["draft"] or current_release["prerelease"]:
        raise CheckFailure("Maintenance requires an existing stable GitHub release.")
    # Assemble under a commit-specific reference before modifying any public version.
    candidate = f"release-{commit}"
    command(["docker", "buildx", "imagetools", "create", "--tag", f"{image}:{candidate}",
             *[f"{image}@{row['digest']}" for row in reports]])
    tested = registry_manifest(package, candidate, anonymous=True)
    if tested is None:
        raise CheckFailure("Tested index is not public.")
    verify_index(tested["manifest"], reports)
    existing = registry_manifest(package, str(version))
    with tempfile.TemporaryDirectory(prefix="kqc-maintain-") as temporary:
        base = Path(temporary)
        asset = base / "release-manifest.json"
        has_asset = any(item["name"] == asset.name for item in current_release["assets"])
        previous = None
        if has_asset:
            command(["gh", "release", "download", tag, "--repo", repository,
                     "--pattern", asset.name, "--dir", str(base)])
            previous = json.loads(asset.read_text())
        if tag == "v2.0.0":
            if previous is None:
                raise CheckFailure("Original v2 release manifest must exist before replacement.")
            guard_replacement(previous, existing, commit, tested["digest"])
            archive_name = f"release-manifest.previous-{ORIGINAL_V2[:12]}.json"
            if previous["commit"] == ORIGINAL_V2:
                archive = base / archive_name
                write_json(archive, previous)
                command(["gh", "release", "upload", tag, str(archive), "--repo", repository, "--clobber"])
            elif not any(item["name"] == archive_name for item in current_release["assets"]):
                raise CheckFailure("The original manifest archive is missing.")
            command(["docker", "buildx", "imagetools", "create", "--tag",
                     f"{image}:previous-2.0.0-{ORIGINAL_V2[:12]}", f"{image}@{ORIGINAL_DIGEST}"])
            # Preserve the exact old tag object before the narrowly authorized move.
            ref = json.loads(command(["gh", "api", f"repos/{repository}/git/ref/tags/{tag}"]).stdout)
            old_commit = json.loads(command(["gh", "api", f"repos/{repository}/commits/{tag}"]).stdout)["sha"]
            if old_commit not in (ORIGINAL_V2, commit):
                raise CheckFailure("Remote v2 tag changed unexpectedly during publication.")
            if old_commit == ORIGINAL_V2:
                archive_ref = "tags/archive/v2.0.0-initial"
                remote = command(["git", "ls-remote", "origin", f"refs/{archive_ref}"], root=source).stdout.strip()
                if not remote:
                    command(["gh", "api", "--method", "POST", f"repos/{repository}/git/refs",
                             "-f", f"ref=refs/{archive_ref}", "-f", f"sha={ref['object']['sha']}"])
                elif remote.split()[0] != ref["object"]["sha"]:
                    raise CheckFailure("Existing archive tag does not match original release.")
                annotated = json.loads(command(["gh", "api", "--method", "POST", f"repos/{repository}/git/tags",
                                               "-f", f"tag={tag}", "-f", f"message={tag}: reviewed repository layout",
                                               "-f", f"object={commit}", "-f", "type=commit"]).stdout)
                command(["gh", "api", "--method", "PATCH", f"repos/{repository}/git/refs/tags/{tag}",
                         "-f", f"sha={annotated['sha']}", "-F", "force=true"])
        else:
            if existing is not None:
                verify_index(existing["manifest"], reports)
            if previous is not None and any(previous.get(key) != value for key, value in (
                ("commit", commit), ("version", str(version)), ("image", image), ("digest", tested["digest"]),
            )):
                raise CheckFailure("Historical GitHub manifest conflicts with tested source/image.")
        command(["docker", "buildx", "imagetools", "create", "--tag", f"{image}:{version}",
                 f"{image}@{tested['digest']}"])
        if registry_manifest(package, str(version), anonymous=True)["digest"] != tested["digest"]:
            raise CheckFailure("Public version does not match tested index.")
        manifest = {"version": str(version), "commit": commit, "image": image,
                    "digest": tested["digest"], "platforms": reports,
                    "workflow": f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}"}
        if tag == "v2.0.0":
            manifest["replaces"] = {"commit": ORIGINAL_V2, "digest": ORIGINAL_DIGEST}
            notes_text = release_notes(version, repository, commit, tested["digest"])
            notes_text += ("\nThe reviewed repository layout replaces the initial v2.0.0 publication. "
                           "Its original manifest is retained as a separate release asset and its source "
                           "as `archive/v2.0.0-initial`. Pull the image again to refresh a cached v2.0.0.\n")
        else:
            original_notes = (current_release["body"] or "").split("\n<!-- container-backfill -->", 1)[0]
            notes_text = (original_notes + "\n<!-- container-backfill -->\n\n"
                          f"Container: `{image}:{version}` (Linux AMD64 and ARM64).\n\n"
                          f"Immutable image: `{image}@{tested['digest']}`\n\n"
                          f"Built from unchanged source `{commit}`. See `release-manifest.json` "
                          "for architecture digests, resolved dependencies, and validation run.\n")
        write_json(asset, manifest)
        notes = base / "notes.md"
        notes.write_text(notes_text)
        command(["gh", "release", "upload", tag, str(asset), "--repo", repository, "--clobber"])
        selected = aliases(version, releases)
        for alias in selected:
            command(["docker", "buildx", "imagetools", "create", "--tag", f"{image}:{alias}",
                     f"{image}@{tested['digest']}"])
            if registry_manifest(package, alias, anonymous=True)["digest"] != tested["digest"]:
                raise CheckFailure(f"Alias {alias} does not match release.")
        command(["gh", "release", "edit", tag, "--repo", repository, "--notes-file", str(notes),
                 "--latest=" + str("latest" in selected).lower()])
    print(f"Published {tag}: {image}@{tested['digest']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["image", "finish"])
    parser.add_argument("--tag", required=True, choices=[*HISTORICAL, "v2.0.0"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--platform")
    parser.add_argument("--output", type=Path, default=ROOT / ".release/maintenance")
    args = parser.parse_args()
    if args.stage == "image":
        image_stage(args.tag, args.source.resolve(), args.platform, args.output.resolve())
    else:
        finish_stage(args.tag, args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    try:
        main()
    except (CheckFailure, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"Maintenance publication stopped: {exc}", file=sys.stderr)
        sys.exit(1)
