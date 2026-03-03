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

## Native Installation

If you wish to run the script natively on your machine, you can follow the instructions below. If you prefer to run
the script in a Docker container, see the next section.

### Prerequisites

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

### Setup

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

#### Problems getting this tool to run under Windows natively?

If you're having trouble getting the script to run under Windows, you could try running under Windows Subsystem for 
Linux (WSL). This is a feature of Windows that allows you to run a Linux environment directly on Windows. You can 
install WSL by following the instructions here: https://docs.microsoft.com/en-us/windows/wsl/install. Form within WSL,
you can follow the instructions above for macOS and Linux.

## Model Context Protocol (MCP) Wrapper

A technical guide for the MCP wrapper can be found in [README-MCP.md](README-MCP.md).

### Usage

The MCP wrapper can be run directly with Python or via Docker.

**Directly:**
```bash
echo '{"action": "AUTH_STATUS"}' | python mcp.py
```

**Docker (macOS / Linux / Windows with WSL):**
```bash
echo '{"action": "AUTH_STATUS"}' | ./docker-mcp.sh
```

**Docker (Windows Command Prompt):**
```cmd
echo {"action": "AUTH_STATUS"} | docker-mcp.bat
```

#### Step 1: Authenticate with the Azure CLI

To use the script, first authenticate using the Azure Cli
```bash
az login
```

Login with an account that has access to the Azure Data Explorer cluster you want to query.

#### Step 2: Activate the Python Virtual Environment

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

#### Step 3: Run the Script

Still in the script's directory in your terminal or command prompt, run the command that corresponds to the output 
format you want.

You can provide the query in three ways:
1.  **Query File:** Using the `--queryFile` argument.
2.  **Query String:** Using the `--query` argument.
3.  **Standard Input (stdin):** Piping the query to the script.

**macOS / Linux / Windows with WSL**  
```bash
# Output to CSV using a query file
python k2csv.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON using a query string
python k2json.py --query "MyTable | limit 10" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON piping from stdin
echo "MyTable | count" | python k2json.py --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

**Windows**  
```cmd
# Output to CSV using a query file
python k2csv.py --queryFile "C:\path\to\query\file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON using a query string
python k2json.py --query "MyTable | limit 10" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"

# Output to JSON piping from stdin
echo MyTable ^| count | python k2json.py --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

> **Note:** The first time you run the script, it might take a few seconds for authentication to complete. Subsequent runs 
  within a reasonable time of each other should be faster.

When the script runs, it will output the results of the query to the terminal in the format you specified. If you would 
like to save the output to a file, you can redirect the output to a file using the `>` operator. For example:

**macOS / Linux / Windows with WSL**  
```bash
# Output to CSV using a query file
python k2csv.py --queryFile "/path/to/query/file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

**Windows**  
```cmd
# Output to CSV using a query file
python k2csv.py --queryFile "C:\path\to\query\file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

## Running in a Docker Container

If you prefer to run the script in a Docker container, you can use the provided `Dockerfile` to build an image and
run a container. This is a good option if you don't want to install Python and the Azure CLI on your machine.

### Prerequisites

Before you begin, ensure you have Docker installed on your system. You can download Docker Desktop from
https://www.docker.com/products/docker-desktop.

### Building the Docker Image

To build the Docker image, navigate to the root of the project directory in your terminal or command prompt and run the
following command:

**macOS / Linux / Windows with WSL**  
```bash
docker compose build
```

**Windows**  
```cmd
docker compose build
```

### Azure Authentication

If your account is associated with multiple tenants, the Azure CLI will prompt you to select the correct subscription and tenant after logging in. 

For example:

```text
No     Subscription name         Subscription ID                       Tenant
-----  ------------------------  ------------------------------------  --------
[1] *  contoso-dev-subscription  8a3b2c1d-4e5f-6g7h-8i9j-0k1l2m3n4o5p  contoso
[2]    contoso-prod-subscription 1b2c3d4e-5f6g-7h8i-9j0k-1l2m3n4o5p6q  contoso
[3]    fabrikam-dev-subscription 3c4d5e6f-7h8i-9j0k-1l2m-3n4o5p6q7r8s  fabrikam
[4]    fabrikam-prod-subscription 5e6f7g8h-9i0j-1k2l-3m4n-5o6p7q8r9s0t  fabrikam

The default is marked with an *; the default tenant is 'contoso' and subscription is 'contoso-dev-subscription' (8a3b2c1d-4e5f-6g7h-8i9j-0k1l2m3n4o5p).

Select a subscription and tenant (Type a number or Enter for no changes): 4
```

Selecting the correct subscription and tenant ensures that the scripts have the necessary permissions to access the Azure Data Explorer cluster.

### Running the Scripts via the Docker Container

#### Step 1: Authenticate with the Azure CLI

To use the script, first authenticate using the Azure Cli

**macOS / Linux / Windows with WSL**
```bash
./docker-run.sh az login
```

**Windows**
```cmd
docker-run.bat az login
```

Login with an account that has access to the Azure Data Explorer cluster you want to query. 

Authentication will be persisted in the Docker container using a Docker volume. This means you only need to authenticate
once per container (until the volume is removed or your credentials expire).

To force dropping the active login:

**macOS / Linux / Windows with WSL**
```bash
./docker-run.sh az logout
```

**Windows**
```cmd
docker-run.bat az logout
```

You can also force the container to forget your credentials by removing the volume. To do this, run the 
following command:

**macOS / Linux / Windows with WSL**
```bash
./docker-run.sh down --volumes
```

**Windows**
```cmd
docker-run.bat down --volumes
```

#### Step 2: Run the Script

> **Note:** For the docker version, all queries you run must be placed in the **./queries** directory. The script 
> will look for the query file in that directory exclusively!

To run the script via the Docker container, use the following command:

**macOS / Linux / Windows with WSL**  
```bash
# JSON
./docker-run.sh python k2json.py --queryFile "./queries/query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
# CSV
./docker-run.sh python k2csv.py --queryFile "./queries/query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

**Windows**  
```cmd
# JSON
docker-run.bat python k2json.py --queryFile ".\queries\query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
# CSV
docker-run.bat python k2csv.py --queryFile ".\queries\query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>"
```

### Using a SOCKS Proxy

If you need to connect through a SOCKS proxy, you can use the following arguments:

*   `--use-socks5 <host>:<port>`: Specify the SOCKS5 proxy server.
*   `--use-socks5-dns`: (Optional) Use the proxy for DNS resolution. This is recommended if your local machine cannot 
    resolve the ADX cluster address (equivalent to using `socks5h://`).

**Example with SOCKS5 proxy:**
```bash
python k2json.py --queryFile "./queries/query.kql" --database "my_db" --adxUrl "https://mycluster.kusto.windows.net" --use-socks5 localhost:1080 --use-socks5-dns
```

#### Azure CLI Login and Proxies

The `az login` command requires opening a browser for authentication.
*   If your browser is not configured to use the same proxy, the authentication might fail.
*   In such cases, you can open the URL provided your phone or another computer with network access to the cluster network:
    ```bash
    az login --use-device-code
    ```
*   Alternatively, ensure your browser is configured to use the proxy or has access to the Microsoft login endpoints required 
    for your ADX cluster. The Firefox browser is known to work with easily with a proxy. In Firefox, open settings then search 
    for "proxy" and set the proxy to "Manual proxy configuration" to the SOCKS5 server address and port.

> **Note:** The first time you run the script, it might take a few seconds for authentication to complete. Subsequent 
  runs within a reasonable time of each other should be faster.

The output of the script will be printed to the terminal. If you would like to save the output to a file, you can
redirect the output to a file using the `>` operator. For example:

**macOS / Linux / Windows with WSL**  
```bash
docker compose run -rm kusto-query-cli python k2json.py --queryFile "./queries/query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

**Windows**  
```cmd
docker compose run -rm kusto-query-cli python k2json.py --queryFile ".\queries\query-file" --database "name-of-database-to-query" --adxUrl "https://<cluster-address>" > output.csv
```

## Test ADX Cluster

This script can be tested against the free and public Help cluster provided by Microsoft.
The URL of that cluster is `https://help.kusto.windows.net`.  This cluster is available to all.
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
python k2json.py --queryFile "./queries/example-find-my-partner-simple-query.kql" --database "FindMyPartner" --adxUrl "https://help.kusto.windows.net"
```

