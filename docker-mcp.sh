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

# Optional explicit container name. If not provided, we let Docker choose a random
# name so multiple instances can run concurrently.
MCP_CONTAINER_NAME="${MCP_CONTAINER_NAME:-}"

# Use a stable/shared Azure CLI state volume by default so auth persists across runs.
# Can be overridden by setting AZURE_STATE_VOLUME.
AZURE_STATE_VOLUME="${AZURE_STATE_VOLUME:-kusto-query-cli-mcp-azure-state}"

# Optional: allow overriding logging controls via .env if not set in the environment
if [ -z "$MCP_LOG_LEVEL" ] && [ -f "$ENV_FILE" ]; then
  MCP_LOG_LEVEL=$(grep -E '^MCP_LOG_LEVEL=' "$ENV_FILE" | cut -d'=' -f2)
fi
if [ -z "$MCP_LOG_PAYLOADS" ] && [ -f "$ENV_FILE" ]; then
  MCP_LOG_PAYLOADS=$(grep -E '^MCP_LOG_PAYLOADS=' "$ENV_FILE" | cut -d'=' -f2)
fi

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

# Prepare optional --name flag only if MCP_CONTAINER_NAME is explicitly set
NAME_FLAG=()
if [ -n "$MCP_CONTAINER_NAME" ]; then
  NAME_FLAG=(--name "$MCP_CONTAINER_NAME")
fi

# Optional env passthrough for logging controls
# If set in the host environment, propagate to the container.
ENV_FLAGS=()
if [ -n "$MCP_LOG_LEVEL" ]; then
  ENV_FLAGS+=( -e "MCP_LOG_LEVEL=$MCP_LOG_LEVEL" )
fi
if [ -n "$MCP_LOG_PAYLOADS" ]; then
  ENV_FLAGS+=( -e "MCP_LOG_PAYLOADS=$MCP_LOG_PAYLOADS" )
fi

# Run the MCP stdio server in the foreground with stdio attached
exec docker run --rm -i \
  "${NAME_FLAG[@]}" \
  "${ENV_FLAGS[@]}" \
  -v "${AZURE_STATE_VOLUME}:/root/.azure" \
  "$IMAGE_TAG" \
  python mcp-stdio-server.py "$@"
