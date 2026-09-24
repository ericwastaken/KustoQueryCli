#!/bin/bash
# Resolve one runtime image. Only the reference is written to stdout.
set -e
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
FORCE_FLAG="${1:-}"

if [ -n "${KQC_IMAGE:-}" ]; then
    if [ "$FORCE_FLAG" = "--force" ]; then
        echo "Error: --force rebuilds local images and cannot be used with KQC_IMAGE. Unset KQC_IMAGE to build locally." >&2
        exit 1
    fi
    if ! docker image inspect "$KQC_IMAGE" >/dev/null 2>&1; then
        echo "Pulling selected image $KQC_IMAGE..." >&2
        if ! docker pull "$KQC_IMAGE" >&2; then
            echo "Error: cannot pull KQC_IMAGE=$KQC_IMAGE. No local build was attempted." >&2
            exit 1
        fi
    fi
    printf '%s\n' "$KQC_IMAGE"
else
    if [ "$FORCE_FLAG" = "--force" ]; then
        "$ROOT/docker-mcp-build.sh" --force
    else
        "$ROOT/docker-mcp-build.sh"
    fi
fi
