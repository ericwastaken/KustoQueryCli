# Azure Data Explorer (ADX) Query Utility

This utility allows you to execute queries against an Azure Data Explorer (ADX) database and output the results in various formats directly to stdout. The script is written in Python and uses the `azure-kusto-data` package to interact with the ADX cluster.

## Motivation

This utility is a simple and short demonstration of using the Azure Python SDK for querying data from ADX.

A much better and far more complete option is the Kusto CLI available at https://learn.microsoft.com/en-us/azure/data-explorer/kusto/tools/kusto-cli. 

## Authentication

This script authenticates using the Azure CLI. You must be logged in to the Azure CLI with an account that has access to the Azure Data Explorer cluster you are querying.

## Prerequisites

Before you begin, ensure you have Python installed on your system. This script was developed with Python 3.8, but it should work with Python 3.6 and above. You also need `pip` for installing Python packages.

## Setup

To set up your environment to run the script, follow these steps:

1. **Clone the repository or download the project**  
   If you have `git` installed, you can clone the repository using:  
   `git clone <repository-url>`

2. **Configure a Python Virtual Environment**
   Navigate to the root of the project directory and run the following commands:

   **macOS/Linux**  
   ```bash
   python3 -m venv ./venv
   source ./venv/bin/activate
   ```
   
    **Windows**  
    ```cmd
    python -m venv venv
    venv\Scripts\activate.bat
    ```

3. **Install dependencies**  
   Navigate to the directory containing `requirements.txt` and run the following command:  
   `pip install -r requirements.txt`  
   This will install the necessary Python packages listed in `requirements.txt`.

4. **Install the Azure CLI**
   Install the Azure CLI for your environment. Instructions here: https://learn.microsoft.com/en-us/cli/azure/

## Usage

To use the script, first authenticate using the Azure Cli
```bash
az login
```

Login with an account that has access to the Azure Data Explorer cluster you want to query.

Then navigate to the script's directory in your terminal or command prompt and run the command that corresponds to the output format you want:

```bash
# Output to CSV
python k2csv.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON
python k2json.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

> **Note:** The first time you run the script, it might take a few seconds for authentication to complete. Subsequent runs within a reasonable time of each other should be faster.

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

