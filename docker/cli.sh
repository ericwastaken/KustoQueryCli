#!/bin/bash
# Launch the CLI runtime using a local build or explicit KQC_IMAGE.
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
cd "$ROOT"

# Compose lifecycle operations do not acquire or build an image.
if [ "${1:-}" = "down" ]; then
    shift
    exec docker compose --project-directory "$ROOT" --env-file "$SCRIPT_DIR/.env" -f "$SCRIPT_DIR/compose.yaml" down "$@"
fi

FORCE_FLAG=""
if [ "${1:-}" = "--force" ]; then
    FORCE_FLAG="--force"
    shift
fi
KQC_RUNTIME_IMAGE="$("$SCRIPT_DIR/lib/acquire-image.sh" "$FORCE_FLAG")"
export KQC_RUNTIME_IMAGE
# The runtime Compose file has no build definition, so execution cannot build.
exec docker compose --project-directory "$ROOT" --env-file "$SCRIPT_DIR/.env" -f "$SCRIPT_DIR/compose.yaml" run --rm --pull never kusto-query-cli "$@"
