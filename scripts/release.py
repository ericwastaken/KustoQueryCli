"""Interactive release preparation. No commits, tags, pushes, or publication."""

import argparse
from datetime import datetime, timezone
import fnmatch
import fcntl
from functools import total_ordering
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid

from release_checks import (
    CheckFailure, ROOT, Runner, check_docker, check_metadata, check_python,
    find_python, matrix, write_json,
)


@total_ordering
class Version:


    def __init__(self, text):
        match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(rc)\.([1-9]\d*))?", text)
        if not match:
            raise CheckFailure("Use X.Y.Z or X.Y.Z-rc.N (no leading zeroes or build metadata).")
        self.core = tuple(int(match[index]) for index in (1, 2, 3))
        self.rc = int(match[5]) if match[5] else None
        self.text = ".".join(map(str, self.core)) + (f"-rc.{self.rc}" if self.rc else "")


    def __str__(self):
        return self.text


    def key(self):
        return (*self.core, self.rc is None, self.rc or 0)


    def __eq__(self, other):
        return isinstance(other, Version) and self.key() == other.key()


    def __lt__(self, other):
        return self.key() < other.key()


def recommend(current, published, messages):
    if current not in published:
        return current, "The working version has not been released yet."
    if current.rc:
        return Version(".".join(map(str, current.core))), "Finalize the current release candidate."
    major, minor, patch = current.core
    if re.search(r"BREAKING[ -]CHANGE:|^\w+(?:\([^)]*\))?!:", messages, re.MULTILINE):
        return Version(f"{major + 1}.0.0"), "Commit messages identify a breaking change."
    if re.search(r"^feat(?:\([^)]*\))?:", messages, re.MULTILINE):
        return Version(f"{major}.{minor + 1}.0"), "Commit messages identify a backward-compatible feature."
    return Version(f"{major}.{minor}.{patch + 1}"), "Default patch increment; review whether the changes warrant a minor or major release."


def command(args, root=ROOT, allowed=(0,)):
    result = subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=120)
    if result.returncode not in allowed:
        raise CheckFailure(f"{shlex.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def git(*args, root=ROOT):
    return command(["git", *args], root).stdout.strip()


def api(path, root=ROOT):
    return json.loads(command(["gh", "api", "--paginate", "--slurp", path], root).stdout)


def repository(root):
    remote = git("remote", "get-url", "origin", root=root)
    match = re.search(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", remote)
    if not match:
        raise CheckFailure("Cannot determine owner/repository from origin.")
    slug = f"{match[1]}/{match[2]}"
    info = api(f"repos/{slug}", root)[0]
    if not info.get("permissions", {}).get("push"):
        raise CheckFailure("The active gh account needs repository write access to check draft releases. Use gh auth status / gh auth switch, then retry.")
    return info


def untracked_inputs(root):
    paths = git("ls-files", "--others", "--exclude-standard", "-z", root=root).split("\0")
    patterns = [line[1:].strip() for line in (root / ".dockerignore").read_text().splitlines() if line.startswith("!")]
    unsafe = []
    for path in filter(None, paths):
        if "__pycache__" in Path(path).parts or path.endswith(".pyc"):
            continue
        included = any(fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("/") + "/") for pattern in patterns)
        if included or path.startswith(("tests/", "scripts/", ".github/")) or path.endswith((".py", ".sh")):
            unsafe.append(path)
    if paths != [""]:
        print("Untracked files are excluded from the validation snapshot.")
    if unsafe:
        raise CheckFailure("Commit or move untracked release inputs first: " + ", ".join(unsafe))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_worktree(root, state):
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        path = Path(git("rev-parse", "--git-path", marker, root=root))
        if (root / path).exists():
            raise CheckFailure(f"Finish or abort the existing Git operation ({marker}) first.")
    if not git("branch", "--show-current", root=root):
        raise CheckFailure("Check out a branch before preparing a release.")
    changed = set(filter(None, git("diff", "--name-only", "-z", "HEAD", root=root).split("\0")))
    if changed:
        if not state or state["head"] != git("rev-parse", "HEAD", root=root):
            raise CheckFailure("Commit or stash tracked changes before preparing a release.")
        for name in changed:
            expected = state["files"].get(name)
            if expected is None or not (root / name).is_file():
                raise CheckFailure(f"Unrelated tracked change: {name}")
            # Release notes are intentionally editable between validation runs.
            if name != "CHANGELOG.md" and digest(root / name) not in expected:
                raise CheckFailure(f"Unexpected edits to prepared metadata: {name}")
    untracked_inputs(root)


def check_conflicts(root, repo, version, releases):
    tag = f"v{version}"
    if tag in git("tag", "--list", root=root).splitlines():
        raise CheckFailure(f"Version conflict: Git tag {tag} already exists.")
    if any(release["tag_name"] == tag for release in releases):
        raise CheckFailure(f"Version conflict: GitHub release {tag} already exists (including drafts).")
    image = f"ghcr.io/{repo.lower()}:{version}"
    result = command(["docker", "buildx", "imagetools", "inspect", image], root, allowed=(0, 1))
    if result.returncode == 0:
        raise CheckFailure(f"Version conflict: {image} already exists.")
    error = (result.stderr + result.stdout).strip().lower()
    denied = any(text in error for text in ("unauthorized", "forbidden", "denied", "failed to authorize"))
    absent = "manifest unknown" in error or "manifest_unknown" in error or error == f"error: {image}: not found"
    if denied or not absent:
        raise CheckFailure(
            f"GHCR conflict check incomplete for {image}: {result.stderr.strip()}. "
            "Verify Docker's GHCR login and package read access, then retry. "
            "An authorization failure, including for a package not created yet, does not prove a version is free."
        )
    return image


def prepare_files(root, target, subjects):
    # Always derive generated metadata from HEAD, allowing interrupted runs to resume.
    original = git("show", "HEAD:mcp-wrapper-version", root=root)
    changes = {}
    names = ["mcp-wrapper-version", "mcp-manifest.json", ".env"]
    names += [str(path.relative_to(root)) for path in sorted((root / "examples").glob("*.json"))]
    for name in names:
        text = command(["git", "show", f"HEAD:{name}"], root).stdout
        if name == "mcp-wrapper-version":
            updated = f"{target}\n"
        elif name == "mcp-manifest.json":
            updated = re.sub(r'("version":\s*")[^"]+(")', lambda match: match[1] + str(target) + match[2], text, count=1)
        elif name == ".env":
            updated = re.sub(r"(?m)^KUSTO_QUERY_CLI_VERSION=.*$", f"KUSTO_QUERY_CLI_VERSION={target}", text)
        else:
            updated = text.replace(f'"wrapper_version": "{original}"', f'"wrapper_version": "{target}"')
            updated = updated.replace(f"kusto-query-cli:{original}", f"kusto-query-cli:{target}")
        if updated != text:
            changes[name] = updated
    notes = (root / "CHANGELOG.md").read_text()
    if f"## {target}\n" not in notes:
        bullets = "\n".join(f"- {line}" for line in subjects.splitlines() if line.strip())
        bullets = bullets or "- Review and describe the changes included in this release."
        notes = notes.replace("# Changelog\n", f"# Changelog\n\n## {target}\n\n{bullets}\n", 1)
        changes["CHANGELOG.md"] = notes
    return changes


def apply_preparation(root, version, changes, previous):
    state = {"head": git("rev-parse", "HEAD", root=root), "version": str(version), "files": {}}
    if previous and previous["head"] == state["head"] and previous["version"] == state["version"]:
        state["files"].update(previous["files"])
    for name, content in changes.items():
        state["files"][name] = [digest(root / name), hashlib.sha256(content.encode()).hexdigest()]
    # Write recovery information before the first source edit.
    write_json(root / ".release/preparation.json", state)
    for name, content in changes.items():
        path = root / name
        temporary = path.with_name(path.name + ".release-tmp")
        temporary.write_text(content)
        temporary.replace(path)
    return state


def tracked_paths(root):
    return [Path(name) for name in git("ls-files", "-z", root=root).split("\0") if name]


def fingerprint(root):
    value = hashlib.sha256()
    for path in tracked_paths(root):
        if (root / path).is_symlink():
            raise CheckFailure(f"Release snapshot does not support symlink input: {path}")
        value.update(str(path).encode() + b"\0")
        value.update(str((root / path).stat().st_mode).encode() + b"\0")
        value.update((root / path).read_bytes())
    return value.hexdigest()


def snapshot(root, destination):
    for relative in tracked_paths(root):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)


def instructions(repo, version, base_branch):
    tag = f"v{version}"
    return (
        f"Review git diff and CHANGELOG.md, then commit the prepared files on a release branch.\n"
        f"Push the branch and open a PR against {base_branch}. Merge only after CI passes.\n"
        f"After merge, update your local {base_branch} and verify its version is {version}:\n\n"
        f"    git switch {shlex.quote(base_branch)}\n"
        f"    git pull --ff-only origin {shlex.quote(base_branch)}\n"
        f"    cat mcp-wrapper-version\n"
        f"    ./build-for-release.sh --check-only --non-interactive --version {version} --base-branch {shlex.quote(base_branch)}\n"
        f"    git tag -a {tag} -m 'Release {tag}'\n"
        f"    git push origin {tag}\n\n"
        f"Expected image: ghcr.io/{repo.lower()}:{version}\n"
        "Watch the Release workflow: it validates uploaded images and publishes the matching GitHub release.\n"
        "For a new GHCR package, set its visibility to public and rerun failed jobs if instructed.\n"
        "These local checks are preparation evidence; GitHub must test and publish the final merged commit.\n"
    )


def eligible_for_latest(target, releases):
    stable = []
    for item in releases:
        if item.get("draft") or item.get("prerelease"):
            continue
        try:
            version = Version(item["tag_name"])
        except CheckFailure:
            continue
        if version.rc is None:
            stable.append(version)
    return target.rc is None and (not stable or target > max(stable))


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Target version, e.g. 1.3.1 or 1.4.0-rc.1")
    parser.add_argument("--check-only", action="store_true", help="Validate the current prepared version without editing tracked files")
    parser.add_argument("--non-interactive", action="store_true", help="Require --version and never prompt")
    parser.add_argument("--base-branch", help="Remote target branch (default: GitHub default branch); set for maintenance releases")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        parser.error("Python 3.12+ is required; set KQC_RELEASE_PYTHON to a suitable interpreter")
    if args.non_interactive and not args.version:
        parser.error("--non-interactive requires --version")
    output = root / ".release/runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    report = {"status": "incomplete", "checks": [], "images": [], "live_azure_tested": False}
    runner = None
    lock = None
    try:
        lock = (root / ".release/preparation.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CheckFailure("Another release preparation is running in this checkout.") from None
        for tool in ("git", "gh", "docker"):
            if not shutil.which(tool):
                raise CheckFailure(f"Required tool is missing: {tool}")
        state_path = root / ".release/preparation.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        check_worktree(root, state)
        command(["gh", "auth", "status"], root)
        info = repository(root)
        repo = info["full_name"]
        base = args.base_branch or info["default_branch"]
        command(["git", "check-ref-format", "--branch", base], root)
        git("fetch", "--prune", "origin", "--tags", root=root)
        ref = f"refs/remotes/origin/{base}"
        if command(["git", "merge-base", "--is-ancestor", ref, "HEAD"], root, allowed=(0, 1)).returncode:
            raise CheckFailure(f"Bring this branch up to date with origin/{base} first.")
        releases = [release for page in api(f"repos/{repo}/releases?per_page=100", root) for release in page]
        published = []
        for text in [release["tag_name"] for release in releases] + git("tag", "--list", root=root).splitlines():
            try:
                published.append(Version(text))
            except CheckFailure:
                continue
        current = Version((root / "mcp-wrapper-version").read_text().strip())
        original = Version(git("show", "HEAD:mcp-wrapper-version", root=root))
        start = f"v{original}"
        revision = f"{start}..HEAD" if start in git("tag", "--list", root=root).splitlines() else "HEAD"
        messages = git("log", "--format=%B", revision, root=root)
        subjects = git("log", "--format=%s", revision, root=root)
        suggested, reason = recommend(current, published, messages)
        if state and state["head"] == git("rev-parse", "HEAD", root=root):
            suggested, reason = Version(state["version"]), "Resume the previously prepared version."
        print(f"Current: {current}; recommended: {suggested}. {reason}")
        known = sorted({str(version): version for version in published}.values(), reverse=True)
        print("Recent version tags/releases: " + (", ".join(map(str, known[:5])) or "(none)"))
        print("Commits to review:\n" + (subjects or "(none since the current version tag)"))
        selected = args.version
        if not selected:
            if args.check_only:
                selected = str(current)
            elif sys.stdin.isatty():
                selected = input(f"Release version [{suggested}]: ").strip() or str(suggested)
            else:
                raise CheckFailure("No interactive terminal. Supply --version and --non-interactive.")
        target = Version(selected)
        if target < original:
            raise CheckFailure("Target must not precede the version at HEAD; use a maintenance branch for an older release line.")
        if state and state["head"] == git("rev-parse", "HEAD", root=root) and git("diff", "--name-only", "HEAD", root=root) and str(target) != state["version"]:
            raise CheckFailure("Finish or revert the existing preparation before choosing another version.")
        if args.check_only and target != current:
            raise CheckFailure("--check-only requires the target to match the current metadata. Prepare that version first.")
        report.update({"version": str(target), "repository": repo, "head": git("rev-parse", "HEAD", root=root), "base_branch": base})
        report["eligible_for_latest"] = eligible_for_latest(target, releases)
        print(f"Eligible for latest: {report['eligible_for_latest']}")
        command(["docker", "info"], root)
        command(["docker", "buildx", "inspect", "--bootstrap"], root)
        report["image"] = check_conflicts(root, repo, target, releases)
        config = matrix(root)
        interpreters = {row["python"]: find_python(row["python"]) for row in config["python"]}
        if not args.check_only:
            changes = prepare_files(root, target, subjects)
            print("Files to prepare: " + (", ".join(changes) or "(already prepared)"))
            if not args.non_interactive and input(f"Prepare and validate {target}? [y/N]: ").strip().lower() != "y":
                raise CheckFailure("Cancelled; no tracked files changed.")
            apply_preparation(root, target, changes, state)
            print(git("diff", "--stat", root=root))
        check_metadata(root)
        git("diff", "--check", root=root)
        report["source_fingerprint"] = fingerprint(root)
        source = output / "source"
        snapshot(root, source)
        runner = Runner(source, output / "checks")
        for row in config["python"]:
            check_python(runner, row, interpreters[row["python"]])
        for row in config["docker"]:
            report["images"].append(check_docker(runner, row["platform"], interpreters[config["python"][0]["python"]]))
        if fingerprint(root) != report["source_fingerprint"] or git("rev-parse", "HEAD", root=root) != report["head"]:
            raise CheckFailure("Source changed during validation; rerun against the final contents.")
        git("fetch", "--prune", "origin", "--tags", root=root)
        if command(["git", "merge-base", "--is-ancestor", ref, "HEAD"], root, allowed=(0, 1)).returncode:
            raise CheckFailure(f"origin/{base} changed during validation; update and rerun.")
        releases = [release for page in api(f"repos/{repo}/releases?per_page=100", root) for release in page]
        check_conflicts(root, repo, target, releases)
        report["eligible_for_latest"] = eligible_for_latest(target, releases)
        report["status"] = "passed"
        guide = instructions(repo, target, base)
        (output / "NEXT-STEPS.txt").write_text(guide)
        print("\nAll local release checks passed. Review the generated changelog before committing.\n" + guide)
        return 0
    except (CheckFailure, subprocess.SubprocessError, OSError, ValueError, KeyboardInterrupt, EOFError) as exc:
        report["error"] = str(exc) or "Interrupted"
        print(f"Release preparation incomplete: {report['error']}", file=sys.stderr)
        print("Prepared edits, if any, were preserved. Correct the problem and rerun with the same version.", file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.close()
        report["checks"] = runner.results if runner else []
        write_json(output / "report.json", report)
        print(f"Release report: {output / 'report.json'}")


if __name__ == "__main__":
    sys.exit(main())
