#!/bin/bash
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
  echo "Unsupported command"
fi
