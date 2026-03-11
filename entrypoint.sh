#!/bin/bash
# entrypoint.sh: A flexible entrypoint for the Docker container.
# It allows running 'python <args>', 'az <args>', or any other command.

# Check the first argument to decide the action
if [ "$1" = "python" ]; then
  # Execute the Python script
  # Assuming the second argument is the script name, and the rest are script arguments
  python "${@:2}"
elif [ "$1" = "az" ]; then
  # Execute Azure CLI command
  # Pass all arguments except the first one to Azure CLI
  az "${@:2}"
else
  # Just execute the command passed
  "$@"
fi
