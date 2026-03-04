#!/bin/bash

# docker-mcp.sh: Launch the MCP stdio server inside Docker.
# This runs 'python mcp-stdio-server.py' in the foreground with stdio attached,
# suitable for MCP clients that spawn a long-lived stdio process.

set -e

# Always execute from the directory where this script resides so relative paths work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

# Parse arguments: support --force for rebuild; pass all others to the server
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

# Ensure we are in the project root
if [ ! -f "Dockerfile" ]; then
  echo "Error: Dockerfile not found in the current directory." >&2
  exit 1
fi

# Build (if needed) and retrieve the IMAGE_TAG from the build helper to avoid duplication
if [ "$FORCE_REBUILD" -eq 1 ]; then
  IMAGE_TAG="$("$SCRIPT_DIR/docker-mcp-build.sh" --force)"
else
  IMAGE_TAG="$("$SCRIPT_DIR/docker-mcp-build.sh")"
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
  python mcp-stdio-server.py "${PASSTHRU[@]}"
