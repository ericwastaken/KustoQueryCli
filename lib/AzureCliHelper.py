import subprocess
import json


def is_azure_cli_installed():
    """
    Checks if the Azure CLI is installed by attempting to get its version.

    Returns:
        bool: True if Azure CLI is installed, False otherwise.
    """
    try:
        subprocess.run(["az", "--version"], check=True, capture_output=True)
        return True
    except FileNotFoundError:
        return False


def check_azure_cli_logged_in():
    """
    Checks if the user is logged in to the Azure CLI.

    Raises:
        SystemExit: If the Azure CLI is not installed or the user is not logged in.
    """
    if not is_azure_cli_installed():
        raise SystemExit("Error: Azure CLI is not installed. Please install it to proceed.")

    try:
        # Execute 'az account show' to get the current account details
        subprocess.run(["az", "account", "show"], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        # Handle errors (e.g., not logged in)
        raise SystemExit(
            "Error: Not logged in to Azure CLI. Please log in using 'az login' before running this script.")
