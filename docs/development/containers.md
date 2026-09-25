# Change Docker builds and launchers

The Dockerfile in `docker/` builds one application image used by CLI, MCP, and wrapper
consumers. The `docker/Dockerfile.dockerignore` uses an allowlist: adding runtime files requires
updating that list. Keep credentials, caches, release output, and scratch files out
of the build context.

`docker/compose.yaml` is the runtime definition. The developer-only
`docker/compose.build.yaml` adds the repository build context and Dockerfile.
Direct Compose commands must supply `--project-directory . --env-file docker/.env`
and both `-f` files from the repository root; see the local build guide.
The CLI launcher explicitly selects the base file after acquiring an image, so
runtime execution does not inherit the development build configuration.

Image acquisition and session execution are separate. With `KQC_IMAGE` unset,
launchers use/build the local versioned image. With it set, they inspect/pull the
selected reference and never silently build source. See
[Image selection](../containers/use-image.md) and [Local builds](../containers/build-image.md).

## Contracts to preserve

- Keep `docker/` shell and Windows entry points consistent. Bash launchers must work with
    macOS Bash 3.2. Resolve internal paths from the launcher location.
- MCP uses `docker run --rm -i` without a TTY. Protocol stdout must stay clean;
    launch/build diagnostics belong on stderr.
- Preserve Azure state mounts, existing volume names, host-shared auth mode, and
    concurrent MCP sessions. Do not replace persistent state during a rebuild.
- Preserve Compose query-file mounts for CLI usage.
- A selected-image pull failure must stop. `--force` is a local rebuild request
    and must reject a selected `KQC_IMAGE`.
- Keep Docker version tags separate from application-version changes; only release
    preparation updates release metadata.

## Validation

Use the shared checks described in [Testing](testing.md). Container changes need
appropriate launcher tests plus builds and protocol checks for the supported
platforms. Local check images stay local; their IDs are not registry manifest
digests.

The release workflow uses the shared matrix and validates uploaded architecture
images by digest before assembling the public multi-platform image and GitHub
release. See [Release workflow](releases.md). Do not introduce a second implementation of release checks in CI.
