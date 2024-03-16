# Azure Data Explorer Query Utility

This utility allows you to execute queries against an Azure Data Explorer (ADX) database and output the results in various formats directly to stdout. The script is written in Python and uses the `azure-kusto-data` package to interact with the ADX cluster.

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
python k2csv.py --inputQuery "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON
python k2json.py --inputQuery "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

> **Note:** The first time you run the script, it might take a few seconds for authentication to complete. Subsequent runs within a reasonable time of each other should be faster.

## Test Azure Data Explorer

This script can be tested against the free and public Help cluster provided by Microsoft.
The URL of that cluster is `https://help.kusto.windows.net`.

A database in that cluster is called **FindMyPartner** and it has a table called **Partner** that can be queried with:

```text
Partner
| project Partner, PartnerType, Website, Contact, Logo 
| limit 10
```
