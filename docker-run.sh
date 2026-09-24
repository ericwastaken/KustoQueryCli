#!/bin/bash
# Launch the CLI runtime using a local build or explicit KQC_IMAGE.
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

# Compose lifecycle operations do not acquire or build an image.
if [ "${1:-}" = "down" ]; then
    shift
    exec docker compose --project-directory "$SCRIPT_DIR" -f "$SCRIPT_DIR/docker-compose.yml" down "$@"
fi

FORCE_FLAG=""
if [ "${1:-}" = "--force" ]; then
    FORCE_FLAG="--force"
    shift
fi
KQC_RUNTIME_IMAGE="$("$SCRIPT_DIR/scripts/docker/acquire-image.sh" "$FORCE_FLAG")"
export KQC_RUNTIME_IMAGE
# The runtime Compose file has no build definition, so execution cannot build.
exec docker compose --project-directory "$SCRIPT_DIR" -f "$SCRIPT_DIR/docker-compose.yml" run --rm --pull never kusto-query-cli "$@"
