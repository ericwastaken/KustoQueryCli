#!/bin/bash

# docker-run.sh: A wrapper for docker compose run --rm kusto-query-cli
# Ensures the image is built before running the container.

set -e

# The service name from docker-compose.yml
SERVICE_NAME="kusto-query-cli"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
VERSION_FILE="$SCRIPT_DIR/mcp-wrapper-version"
ENV_FILE="$SCRIPT_DIR/.env"

resolve_version() {
  if [ -n "$KUSTO_QUERY_CLI_VERSION" ]; then
    echo "$KUSTO_QUERY_CLI_VERSION"
    return 0
  fi

  if [ -f "$VERSION_FILE" ]; then
    tr -d ' \t\r\n' < "$VERSION_FILE"
    return 0
  fi

  if [ -f "$ENV_FILE" ]; then
    grep -E '^KUSTO_QUERY_CLI_VERSION=' "$ENV_FILE" | cut -d'=' -f2
    return 0
  fi

  return 1
}

# Function to check if the Docker image exists
image_exists() {
  local image_tag

  KUSTO_QUERY_CLI_VERSION="$(resolve_version)"

  if [ -z "$KUSTO_QUERY_CLI_VERSION" ]; then
    echo "Error: unable to resolve KUSTO_QUERY_CLI_VERSION." >&2
    echo "Set KUSTO_QUERY_CLI_VERSION in the environment or update $VERSION_FILE." >&2
    exit 1
  fi
  
  image_tag="kusto-query-cli:${KUSTO_QUERY_CLI_VERSION}"
  
  if [ -z "$image_tag" ]; then
    return 1 # Cannot determine tag, force build
  fi

  if [[ "$(docker images -q "$image_tag" 2> /dev/null)" == "" ]]; then
    return 1 # Image does not exist
  fi
  return 0 # Image exists
}

export KUSTO_QUERY_CLI_VERSION="${KUSTO_QUERY_CLI_VERSION:-$(resolve_version)}"

# Ensure we are in the directory where docker-compose.yml resides
if [ ! -f "docker-compose.yml" ]; then
  echo "Error: docker-compose.yml not found in the current directory." >&2
  exit 1
fi

# Special case for 'down' command
if [ "$1" = "down" ]; then
  shift
  echo "Running: docker compose down $*"
  docker compose down "$@"
  exit 0
fi

# Check if image needs building
if ! image_exists; then
  echo "Image for $SERVICE_NAME not found. Building now..."
  if ! docker compose build "$SERVICE_NAME"; then
    echo "Error: Failed to build $SERVICE_NAME." >&2
    exit 1
  fi
fi

# Run the command
echo "Running: docker compose run --rm $SERVICE_NAME $*"
docker compose run --rm "$SERVICE_NAME" "$@"
