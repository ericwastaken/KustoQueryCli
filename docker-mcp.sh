#!/bin/bash

# docker-mcp.sh: A wrapper for running the MCP wrapper inside Docker.
# This script reads from stdin and pipes it to 'python mcp.py' inside a managed container.

set -e

# Always execute from the directory where this script resides so relative paths work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found at $ENV_FILE" >&2
  echo "The .env file must exist and contain KUSTO_QUERY_CLI_VERSION variable." >&2
  exit 1
fi

KUSTO_QUERY_CLI_VERSION=$(grep -E '^KUSTO_QUERY_CLI_VERSION=' "$ENV_FILE" | cut -d'=' -f2)

if [ -z "$KUSTO_QUERY_CLI_VERSION" ]; then
  echo "Error: KUSTO_QUERY_CLI_VERSION not set in $ENV_FILE" >&2
  echo "Please add KUSTO_QUERY_CLI_VERSION=<version> to your .env file." >&2
  exit 1
fi

IMAGE_TAG="kusto-query-cli:${KUSTO_QUERY_CLI_VERSION}"
MCP_CONTAINER_NAME="kusto-query-cli-mcp"
AZURE_STATE_VOLUME="${MCP_CONTAINER_NAME}-azure-state"

image_exists() {
  docker image inspect "$IMAGE_TAG" > /dev/null 2>&1
}

# Ensure we are in the project root
if [ ! -f "Dockerfile" ]; then
  echo "Error: Dockerfile not found in the current directory." >&2
  exit 1
fi

# Check if image needs building
if ! image_exists; then
  echo "Image $IMAGE_TAG not found. Building now..." >&2
  if ! docker build -t "$IMAGE_TAG" .; then
    echo "Error: Failed to build $IMAGE_TAG." >&2
    exit 1
  fi
fi

# MCP mode behavior:
# 1) Use a dedicated container with a fixed name.
# 2) If it exists but is not running, remove and re-run to ensure fresh state/volumes.
# 3) If it's already running, simply use it via 'docker exec'.

is_running="$(docker inspect -f '{{.State.Running}}' "$MCP_CONTAINER_NAME" 2>/dev/null || echo "not_found")"
# Clean up potential whitespace (some docker versions output a newline even on error)
is_running="${is_running//[[:space:]]/}"

if [ "$is_running" != "true" ]; then
  if [ "$is_running" != "not_found" ]; then
    # Container exists but is stopped. Remove it so we can run it with proper config.
    docker rm "$MCP_CONTAINER_NAME" > /dev/null
  fi
  
  # Start the container and keep it alive in background
  docker run -d --name "$MCP_CONTAINER_NAME" \
    -v "${AZURE_STATE_VOLUME}:/root/.azure" \
    "$IMAGE_TAG" \
    tail -f /dev/null > /dev/null
fi

# Always execute the command via exec
docker exec -i "$MCP_CONTAINER_NAME" python mcp.py "$@"
