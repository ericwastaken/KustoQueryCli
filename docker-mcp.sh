#!/bin/bash

# docker-mcp.sh: Launch the MCP stdio server inside Docker.
# This runs 'python mcp-stdio-server.py' in the foreground with stdio attached,
# suitable for MCP clients that spawn a long-lived stdio process.

set -e

# Always execute from the directory where this script resides so relative paths work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

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

# If a stale container exists, remove it so the foreground run can attach the name.
if docker ps -a --format '{{.Names}}' | grep -qx "$MCP_CONTAINER_NAME"; then
  docker rm -f "$MCP_CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Run the MCP stdio server in the foreground with stdio attached
exec docker run --rm -i \
  --name "$MCP_CONTAINER_NAME" \
  -v "${AZURE_STATE_VOLUME}:/root/.azure" \
  "$IMAGE_TAG" \
  python mcp-stdio-server.py "$@"
