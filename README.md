# Azure Data Explorer (ADX) Query Utility

This utility allows you to execute queries against an Azure Data Explorer (ADX) database and output the results in 
various formats directly to stdout. The script is written in Python and uses the `azure-kusto-data` package to 
interact with the ADX cluster.

## Motivation

This utility is a simple and short demonstration of using the Azure Python SDK for querying data from ADX.

A much better and far more complete option is the Kusto CLI available at https://learn.microsoft.com/en-us/azure/data-explorer/kusto/tools/kusto-cli. 

## Authentication

This script authenticates using the Azure CLI. You must be logged in to the Azure CLI with an account that has access 
to the Azure Data Explorer cluster you are querying.

## Prerequisites

Before you begin, ensure you have Python installed on your system. This script was developed with Python 3.8, but it 
should work with Python 3.6 and above. You also need `pip` for installing Python packages.

Under macOS and Linux, Python is usually pre-installed. You can check the version of Python installed on your system 
by running the following command in your terminal:

```bash
python3 --version
```

Under macOS, if you want a more recent version of Python than what is provided by your OS, you can install it using 
Homebrew. See https://docs.brew.sh/Homebrew-and-Python for instructions.

Under Windows, it's possible to install Python and pip from the Microsoft Store. Open the Microsoft Store 
and search for Python. Install the latest version of Python 3.

## Setup

To set up your environment to run the script, follow these steps:

1. **Clone the repository or download the project**  
   If you have `git` installed, you can clone the repository using:  
   `git clone <repository-url>`

2. **Configure a Python Virtual Environment**
   Navigate to the root of the project directory and run the following commands:

   **macOS / Linux / Windows with WSL**  
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   ```
   
   **Windows**  
   ```cmd
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies**  
   After configuring a virttual environment and activating it, navigate to the directory containing `requirements.txt` 
   and run the following command:  
   `pip install -r requirements.txt`  
   This will install the necessary Python packages listed in `requirements.txt`, but inside the virtual environment
   you created above instead of global for your installation of Python.

4. **Install the Azure CLI**
   Install the Azure CLI for your environment. Instructions here: https://learn.microsoft.com/en-us/cli/azure/

### Problems getting this tool to run under Windows?

If you're having trouble getting the script to run under Windows, you could try running under Windows Subsystem for 
Linux (WSL). This is a feature of Windows that allows you to run a Linux environment directly on Windows. You can 
install WSL by following the instructions here: https://docs.microsoft.com/en-us/windows/wsl/install. Form within WSL,
you can follow the instructions above for macOS and Linux.

## Usage

Using this script is simple but requires a few steps.

### Step 1: Authenticate with the Azure CLI

To use the script, first authenticate using the Azure Cli
```bash
az login
```

Login with an account that has access to the Azure Data Explorer cluster you want to query.

### Step 2: Activate the Python Virtual Environment

Navigate to the script's directory in your terminal or command prompt and activate the Python virtual environment 
you created earlier. You only need to do this once per terminal window or command prompt.

**macOS / Linux / Windows with WSL**  
```bash
source ./venv/bin/activate
```

**Windows**  
```cmd
.\venv\Scripts\activate
```

### Step 3: Run the Script

Still in the script's directory in your terminal or command prompt, run the command that corresponds to the output 
format you want:

**macOS / Linux / Windows with WSL**  
```bash
# Output to CSV
python k2csv.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON
python k2json.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

**Windows**  
```cmd
# Output to CSV
python k2csv.py --queryFile "C:\path\to\query\file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
# Output to JSON
python k2json.py --queryFile "C:\path\to\query\file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

> **Note:** The first time you run the script, it might take a few seconds for authentication to complete. Subsequent runs within a reasonable time of each other should be faster.

When the script runs, it will output the results of the query to the terminal in the format you specified. If you would 
like to save the output to a file, you can redirect the output to a file using the `>` operator. For example:

**macOS / Linux / Windows with WSL**  
```bash
python k2csv.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

**Windows**  
```cmd
python k2csv.py --queryFile "C:\path\to\query\file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

## Test ADX Cluster

This script can be tested against the free and public Help cluster provided by Microsoft.
The URL of that cluster is `https://help.kusto.windows.net`.
This cluster is available to all.
Although you'll still need to log in with the Azure CLI, this cluster accepts connections from anyone.

A database in that cluster is called **FindMyPartner**,
and it has a table called **Partner** that can be queried with the following query:

```text
Partner
| project Partner, PartnerType, Website, Contact, Logo 
| limit 10
```

To run this command against the Help cluster, use the following command:

```bash
python k2json.py --queryFile "examples/find-my-partner-simple-query.kql" --database "FindMyPartner" --adxUrl "https://help.kusto.windows.net"
```

