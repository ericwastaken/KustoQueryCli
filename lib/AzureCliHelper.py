import subprocess
import platform
import shlex

"""
This module contains helper functions to check if the Azure CLI is installed and if the user is logged in.
This should work under Linux, macOS, and Windows.
The check is very simple, which is a simple run of the Aure CLI command for the commands 'az --version' and
'az account show'.
"""


def check_azure_cli_logged_in():
    """
    Checks if the user is logged in to the Azure CLI.

    Raises:
        SystemExit: If the Azure CLI is not installed or the user is not logged in.
    """
    # Detect the operating system
    os_name = platform.system().lower()

    if not is_azure_cli_installed(os_name):
        raise SystemExit("Error: Azure CLI is not installed. Please install it to proceed.")

    try:
        # Command to check Azure CLI version
        command = "az account show"

        # If the OS is Windows, modify the command to run it through cmd.exe
        if os_name == "windows":
            # Splitting the command into parts for Windows
            command = shlex.split(f'cmd.exe /c "{command}"')
        else:
            # Use shlex.split to ensure the command is properly split for non-Windows OSes
            command = shlex.split(command)

        # Execute 'az account show' to get the current account details
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    except subprocess.CalledProcessError:
        # Handle errors (e.g., not logged in)
        raise SystemExit(
            "Error: Not logged in to Azure CLI. Please log in using 'az login' before running this script.")


def is_azure_cli_installed(os_name):
    try:
        # Command to check Azure CLI version
        command = "az --version"

        # If the OS is Windows, modify the command to run it through cmd.exe
        if os_name == "windows":
            # Splitting the command into parts for Windows
            command = shlex.split(f'cmd.exe /c "{command}"')
        else:
            # Use shlex.split to ensure the command is properly split for non-Windows OSes
            command = shlex.split(command)

        # Execute the command
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # If the command was successful, Azure CLI is installed
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking Azure CLI installation: {e}")
        return False
