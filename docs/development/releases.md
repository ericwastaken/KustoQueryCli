# Preparing a release

Run `./build-for-release.sh` from any directory. It recommends a version, asks you
to choose one, checks conflicts, previews files, and asks you to start preparation.
It never commits, tags, pushes, or publishes.

Local preparation and GitHub Actions use `scripts/release_checks.py` and the matrix
in `scripts/release-matrix.json`. CI uses native runners for both architectures;
local checks may require Docker emulation for the other architecture.

## Prerequisites

- Python 3.12 and 3.13 on PATH or discoverable through `uv python find --offline`.
    Interpreters are not installed automatically. Checks create isolated environments
    and install dependencies into them.
- Git and GitHub CLI authenticated with repository write access, which is needed
    to see draft releases. Use `gh auth status` and `gh auth switch` to select an account.
- Docker Engine/Desktop and Buildx capable of building and running Linux AMD64 and ARM64.
- Read access to the GHCR package through Docker's registry credentials.

Docker Desktop normally provides cross-architecture execution on macOS. On Linux,
configure emulation or a builder supporting both platforms. Missing prerequisites
and failed checks are failures, never silently skipped gates.

The launcher uses `python3`. Override it with
`KQC_RELEASE_PYTHON=/path/to/python3.12 ./build-for-release.sh` if needed.
Select specific test runtimes with `KQC_PYTHON_312=/path/to/python3.12` and
`KQC_PYTHON_313=/path/to/python3.13`. On Apple Silicon, prefer native ARM Python
installations to avoid incompatible Intel/OpenSSL extension builds.

## Version selection

Use `X.Y.Z` for stable or `X.Y.Z-rc.N` for a candidate. Recommendations use commit
messages since the current version tag: `feat:` suggests minor; `BREAKING CHANGE:`
or `type!:` suggests major; otherwise patch. This is a suggestion, not analysis of
whether code changes are breaking. An unpublished prepared version is recommended unchanged.

Local/fetched remote tags, GitHub releases including drafts, and the exact GHCR tag
must be unused. Registry permission/network errors stop preparation. GHCR can return
403 for a package not created yet; the script reports an incomplete check instead of
assuming the version is free. Authenticate Docker to GHCR for first-time setup;
package visibility is verified again before the publisher announces a release.

For maintenance, check out its branch and pass `--base-branch maintenance/1.2`
(the branch must exist on origin). Its version may be below the latest release but
must not precede its own HEAD version. The report shows eligibility for `latest`.

## Usage

```bash
./build-for-release.sh
./build-for-release.sh --version 1.3.1
./build-for-release.sh --version 1.4.0-rc.1 --non-interactive
./build-for-release.sh --check-only --version 1.3.1 --non-interactive
```

`--non-interactive` requires `--version`, which authorizes preparing metadata.
`--check-only` edits no tracked files and requires the target to match current
metadata. It still fetches refs, checks conflicts, installs test dependencies,
builds images, and writes reports; it is not an offline dry run.

Start on a branch with clean tracked files containing the latest origin base branch.
Commit or move untracked runtime/test/release inputs first. Untracked scratch files
and Python caches are excluded from the tracked-file validation snapshot.

## Checks and results

1. Repository state, remote freshness, version availability, and required tools.
2. Application, manifest, Docker, and canonical response-example versions, plus the
    changelog entry. Usage guides reference canonical metadata instead of copying
    release-version literals into commands.
3. Both configured Python/MCP combinations, all tests, dependency checks, modern and
    legacy sessions, and actual MCP 1.x clients.
4. Both Linux image architectures, Azure CLI, dependencies, and modern/legacy/MCP 1.x
    sessions against each built image's immutable local ID.
5. Unchanged source, refreshed remote state, and version availability again.

Live Azure login and cloud queries are not exercised. Auth/query/proxy regression
checks use mocks. Local image IDs are evidence, not GHCR manifest digests; images
are not uploaded.

Reports, dependency lists, and logs live in `.release/runs/` (Git ignored). Every run
writes `report.json`, with `incomplete` on failure or interruption. Successful runs
also write `NEXT-STEPS.txt`. Images remain under `kusto-query-cli:release-check-*`;
remove these specific images with Docker when no longer needed.

## Recovery

Failed checks preserve prepared edits. Correct the problem and rerun with the same
version; all checks run again. `.release/preparation.json` is written before edits
and permits only recorded metadata changes on a dirty rerun. You may edit the new
changelog entry before rerunning. Other tracked edits still block preparation.

To abandon preparation, review `git diff`, restore only generated files you intend
to discard, and remove `.release/preparation.json`. Once changes are committed, the
next run validates that commit.

## Complete the release

Review the diff and changelog, commit to a release branch, open a PR, and merge after
CI passes. Generated instructions show how to update the base branch, revalidate
that merged version, and create and push the annotated version tag.

Pushing `vX.Y.Z` or `vX.Y.Z-rc.N` triggers `.github/workflows/release.yml`:

1. Verify the tag matches canonical metadata and points to a commit already merged
    into `main` or `maintenance/X.Y`.
2. Run the shared Python/MCP matrix against that tagged commit.
3. Build each architecture on its native runner, upload a commit-specific candidate,
    then pull and validate its immutable registry digest with the shared Docker checks.
4. Combine only the passing architecture digests into the exact version tag and
    verify anonymous registry access.
5. Attach `release-manifest.json` (source commit, index and architecture digests,
    dependencies, and workflow URL) to a matching GitHub release and publish it.

Stable versions update their minor alias only when they are the newest stable
version in that minor series. Only the highest stable version updates `latest`
and becomes GitHub's latest release. Candidates become GitHub prereleases and
never update stable aliases. Main-branch pushes run CI without publishing images.

The workflow uses `GITHUB_TOKEN`, with package write permission in publishing jobs
and repository write permission only in the final job. No long-lived publishing
secret is required. All release runs are serialized to protect mutable aliases.

### First package publication

GitHub creates new GHCR packages as private. After the first candidate upload,
set the `kustoquerycli` package's visibility to public in its GitHub package settings.
The publisher stops before announcing the release if anonymous access fails.
Rerun failed jobs after correcting visibility. This is a one-time registry setup.

### Publishing recovery

Rerun failed jobs, or dispatch the Release workflow with the existing tag. Keep
release tags fixed. Successful commit-specific architecture candidates are reused
and retested rather than rebuilt. Exact version tags are accepted only when they
contain the tested digests; conflicts stop publication. Existing published releases
must have a matching manifest asset and are not rewritten. Draft releases can be
completed after an interrupted upload. GitHub release publication happens last;
a failed run may leave candidate or version images in GHCR before announcement.

Use the workflow URL to inspect failures. Never delete or move a released tag to
make a conflict disappear. Retain referenced candidate manifests because the
multi-platform image depends on their architecture digests.

### Approved v2 layout replacement and historical containers

`Release maintenance` is a narrowly scoped, manual workflow for the initial
v2.0.0 layout correction and container backfills for v1.2.1 and v1.3.0. Dispatch
it from `main` after PR CI passes. It builds both Linux architectures, tests the
uploaded digests, and records resolved dependencies in each release manifest.
The 1.x builds use their original, pinned tag commits and retain their original
release notes. Their minor aliases advance without changing `latest`.

The user explicitly approved replacing the initial v2.0.0 publication with the
reviewed layout under the same version. This is an exception to normal immutable
release tags. The maintenance publisher accepts only the recorded original
source/image or an exact retry of the same replacement. It archives the original
tag as `archive/v2.0.0-initial`, retains the original release manifest as another
asset, and preserves the original image under `previous-2.0.0-<original-commit>`.
The new manifest records what it replaces. Cached v2.0.0 images must be pulled
again. Later releases must use a new version and the normal Release workflow.

If interrupted, rerun the same workflow run so its source SHA remains fixed.
Successful image candidates are reused and retested. Publication is serialized
with normal releases; unrelated tag or image changes stop recovery.
