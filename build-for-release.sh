#!/bin/bash
# Prepare and validate a release. Never commits, tags, pushes, or publishes.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "${KQC_RELEASE_PYTHON:-python3}" "$SCRIPT_DIR/scripts/release.py" "$@"
