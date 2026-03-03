# Kusto Query CLI - MCP Wrapper

This project provides a Model Context Protocol (MCP) wrapper for interacting with Azure Data Explorer (ADX) via the Azure CLI.

## Actions

The MCP wrapper (`mcp.py`) supports the following actions:

### `LOGIN`
Initiates or verifies Azure CLI authentication.
- **Request**: 
  ```json
  {
    "action": "LOGIN",
    "params": {
      "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
  ```
- **Parameters**:
    - `subscription_id` (string, optional): The target Azure subscription ID. If provided, the wrapper will attempt to 
      select this subscription during the login process or switch to it if already authenticated.
- **Behavior**:
    - If already authenticated, returns current subscription and tenant details.
    - If not authenticated, initiates a device code login flow and returns the `verification_url` and `device_code`. 
    - In Docker environments, the login process runs in the background for up to 120 seconds to allow for completion and 
      automated subscription selection.
- **Response**: Standard JSON envelope with `authenticated` status and either account info or device login details.

### `LOGOUT`
Logs out from the current Azure CLI session.
- **Request**: `{"action": "LOGOUT"}`
- **Response**: Standard JSON envelope with `logged_out: true` or an error if the logout process failed.

### `AUTH_STATUS`
Checks the current authentication status.
- **Request**: `{"action": "AUTH_STATUS"}`
- **Response**: Returns `authenticated: true` with account details or `authenticated: false`.

### `QUERY`
Executes a Kusto query against a specific cluster and database.
- **Request**:
  ```json
  {
    "action": "QUERY",
    "params": {
      "query": "Table | limit 10",
      "database": "MyDatabase",
      "cluster_url": "https://mycluster.kusto.windows.net",
      "socks5_proxy": "localhost:1080",
      "socks5_dns": true
    }
  }
  ```
- **Parameters**:
    - `query` (string, required): The KQL query to execute.
    - `database` (string, required): The target database name.
    - `cluster_url` (string, required): The ADX cluster URL.
    - `socks5_proxy` (string, optional): SOCKS5 proxy in `host:port` format.
    - `socks5_dns` (boolean, optional): Whether to use proxy for DNS (defaults to `false`).
- **Response**: Standard JSON envelope containing a list of objects (rows) in the `data.result` field.

## Global Response Envelope

All responses follow this structure:

```json
{
    "status": "success | error",
    "action": "ACTION_NAME",
    "data": { ... },
    "error": {
        "type": "category",
        "code": "MACHINE_READABLE_CODE",
        "message": "Human readable message",
        "details": { ... }
    },
    "metadata": {
        "timestamp": "ISO-8601",
        "execution_time_ms": 123,
        "authenticated": true
    }
}
```

## Error Handling

- **`AZ_CLI_NOT_FOUND`**: Azure CLI is not installed in the environment.
- **`AZ_NOT_AUTHENTICATED`**: Action requires authentication, but the user is not logged in.
- **`AZ_TOKEN_EXPIRED`**: The Azure CLI token has expired.
- **`KUSTO_QUERY_FAILED`**: The Kusto query execution failed (e.g., syntax error).
- **`EXECUTION_TIMEOUT`**: The operation exceeded the internal timeout.
- **`WRAPPER_EXCEPTION`**: Unexpected internal error.

## Environment Variables

- `MCP_DEBUG`: Set to `true` to enable pretty-printed JSON and include detailed error messages.

**Example: Enabling Debug Mode**

To run the MCP wrapper with debug mode enabled on macOS/Linux:

```bash
export MCP_DEBUG=true
echo '{"action": "AUTH_STATUS"}' | python mcp.py
```

On Windows:

```cmd
set MCP_DEBUG=true
echo {"action": "AUTH_STATUS"} | python mcp.py
```

## Usage

Run the script and provide the action JSON via stdin:

```bash
echo '{"action": "AUTH_STATUS"}' | python mcp.py
```

### Docker Usage

You can also run the MCP wrapper using Docker. This ensures that all dependencies, including the Azure CLI, are correctly installed.

**Container Lifecycle**:
When using `docker-mcp.sh` or `docker-mcp.bat`, the container is started in the background (if not already running) and reused for subsequent calls. This is necessary to maintain background processes such as Azure CLI authentication.

To stop the background container and clean up, you can use:
```bash
./docker-run.sh down
```

**macOS / Linux / Windows with WSL**

Use the provided `docker-mcp.sh` script:

```bash
echo '{"action": "AUTH_STATUS"}' | ./docker-mcp.sh
```

**Windows**

Use the provided `docker-mcp.bat` script:

```cmd
echo {"action": "AUTH_STATUS"} | docker-mcp.bat
```

