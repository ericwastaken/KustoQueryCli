#!/bin/bash

# docker-mcp-build.sh: Build the Docker image for the MCP stdio server only.
# Outputs the IMAGE_TAG to stdout on success. All status/errors go to stderr.

set -e

# Always execute from the directory where this script resides so relative paths work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

# This entry point always builds locally. Launchers handle external images.
if [ -n "${KQC_IMAGE:-}" ]; then
  echo "Error: docker-mcp-build.sh builds locally. Unset KQC_IMAGE first, or use a Docker launcher to run the selected image." >&2
  exit 1
fi

# Parse args
FORCE_REBUILD=0
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE_REBUILD=1
      shift
      ;;
    *)
      PASSTHRU+=("$1")
      shift
      ;;
  esac
done

# Resolve version tag priority: env var > mcp-wrapper-version > dev
if [ -z "$KUSTO_QUERY_CLI_VERSION" ]; then
  if [ -f "$SCRIPT_DIR/mcp-wrapper-version" ]; then
    KUSTO_QUERY_CLI_VERSION=$(tr -d ' \t\r\n' < "$SCRIPT_DIR/mcp-wrapper-version")
  else
    KUSTO_QUERY_CLI_VERSION="dev"
  fi
fi

IMAGE_TAG="kusto-query-cli:${KUSTO_QUERY_CLI_VERSION}"

# Ensure we are in the project root
if [ ! -f "Dockerfile" ]; then
  echo "Error: Dockerfile not found in the current directory." >&2
  exit 1
fi

image_exists() {
  docker image inspect "$IMAGE_TAG" > /dev/null 2>&1
}

# Build if image doesn't exist, or always build when forced
if [ "$FORCE_REBUILD" -eq 1 ] || ! image_exists; then
  if [ "$FORCE_REBUILD" -eq 1 ]; then
    echo "Building image $IMAGE_TAG (forced rebuild)..." >&2
  else
    echo "Image $IMAGE_TAG not found. Building now..." >&2
  fi
  if ! docker build -t "$IMAGE_TAG" . >&2; then
    echo "Error: Failed to build $IMAGE_TAG." >&2
    exit 1
  fi
fi

# Output the IMAGE_TAG for callers to consume
echo "$IMAGE_TAG"
