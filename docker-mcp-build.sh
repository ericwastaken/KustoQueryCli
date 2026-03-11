#!/bin/bash

# docker-mcp-build.sh: Build the Docker image for the MCP stdio server only.
# Outputs the IMAGE_TAG to stdout on success. All status/errors go to stderr.

set -e

# Always execute from the directory where this script resides so relative paths work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

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

# Resolve version tag priority: env var > .env > mcp-wrapper-version > dev
if [ -z "$KUSTO_QUERY_CLI_VERSION" ]; then
  if [ -f "$ENV_FILE" ]; then
    KUSTO_QUERY_CLI_VERSION=$(grep -E '^KUSTO_QUERY_CLI_VERSION=' "$ENV_FILE" | cut -d'=' -f2)
  fi
fi

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

# Remove existing image if --force is specified
if [ "$FORCE_REBUILD" -eq 1 ] && image_exists; then
  echo "--force specified: removing existing image $IMAGE_TAG before rebuild..." >&2
  if ! docker rmi -f "$IMAGE_TAG" >/dev/null 2>&1; then
    echo "Warning: Failed to remove existing image $IMAGE_TAG (it may be in use). Proceeding with rebuild." >&2
  fi
fi

# Build if image doesn't exist, or always build when forced
if [ "$FORCE_REBUILD" -eq 1 ] || ! image_exists; then
  if [ "$FORCE_REBUILD" -eq 1 ]; then
    echo "Building image $IMAGE_TAG (forced rebuild)..." >&2
  else
    echo "Image $IMAGE_TAG not found. Building now..." >&2
  fi
  if ! docker build -t "$IMAGE_TAG" .; then
    echo "Error: Failed to build $IMAGE_TAG." >&2
    exit 1
  fi
fi

# Output the IMAGE_TAG for callers to consume
echo "$IMAGE_TAG"
