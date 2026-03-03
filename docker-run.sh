#!/bin/bash

# docker-run.sh: A wrapper for docker compose run --rm kusto-query-cli
# Ensures the image is built before running the container.

set -e

# The service name from docker-compose.yml
SERVICE_NAME="kusto-query-cli"

# Function to check if the Docker image exists
image_exists() {
  local image_tag
  # Extract image tag from docker-compose.yml (line 4: image: kusto-query-cli:1.1.0)
  # We look for the 'image:' key under the service 'kusto-query-cli:'
  image_tag=$(sed -n '/kusto-query-cli:/,/image:/p' docker-compose.yml | grep 'image:' | awk '{print $2}')
  
  if [ -z "$image_tag" ]; then
    return 1 # Cannot determine tag, force build
  fi

  if [[ "$(docker images -q "$image_tag" 2> /dev/null)" == "" ]]; then
    return 1 # Image does not exist
  fi
  return 0 # Image exists
}

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
