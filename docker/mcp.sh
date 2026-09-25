#!/bin/bash

# docker/mcp.sh: Launch the MCP stdio server inside Docker.
# This runs 'python mcp-stdio-server.py' in the foreground with stdio attached,
# suitable for MCP clients that spawn a long-lived stdio process.

set -e

# Resolve the project root independently of the caller's current directory.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
cd "$ROOT"

ENV_FILE="$SCRIPT_DIR/.env"

# Parse arguments: support --force for rebuild, --share-host-azure-state for a
# host bind mount; pass all others to the server.
FORCE_REBUILD=0
SHARE_HOST_AZURE_STATE=0
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE_REBUILD=1
      shift
      ;;
    --share-host-azure-state)
      SHARE_HOST_AZURE_STATE=1
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

AZURE_MOUNT_SOURCE="$AZURE_STATE_VOLUME"
AZURE_AUTH_MODE="container_managed"
if [ "$SHARE_HOST_AZURE_STATE" -eq 1 ]; then
  AZURE_MOUNT_SOURCE="$HOME/.azure"
  AZURE_AUTH_MODE="host_shared"
fi

# Optional: allow overriding logging controls via .env if not set in the environment
if [ -z "$MCP_LOG_LEVEL" ] && [ -f "$ENV_FILE" ]; then
  MCP_LOG_LEVEL=$(grep -E '^MCP_LOG_LEVEL=' "$ENV_FILE" | cut -d'=' -f2)
fi
if [ -z "$MCP_LOG_PAYLOADS" ] && [ -f "$ENV_FILE" ]; then
  MCP_LOG_PAYLOADS=$(grep -E '^MCP_LOG_PAYLOADS=' "$ENV_FILE" | cut -d'=' -f2)
fi

# Image acquisition is independent of mounts and the MCP execution contract.
FORCE_FLAG=""
if [ "$FORCE_REBUILD" -eq 1 ]; then
  FORCE_FLAG="--force"
fi
IMAGE_TAG="$("$SCRIPT_DIR/lib/acquire-image.sh" "$FORCE_FLAG")"

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
ENV_FLAGS+=( -e "MCP_AZURE_AUTH_MODE=$AZURE_AUTH_MODE" )

# Run the MCP stdio server in the foreground with stdio attached
exec docker run --rm -i \
  "${NAME_FLAG[@]}" \
  "${ENV_FLAGS[@]}" \
  -v "${AZURE_MOUNT_SOURCE}:/root/.azure" \
  "$IMAGE_TAG" \
  python mcp-stdio-server.py "${PASSTHRU[@]}"
