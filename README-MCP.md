# Kusto Query CLI - MCP Wrapper

This project provides a Model Context Protocol (MCP) wrapper for interacting with Azure Data Explorer (ADX) via the Azure CLI.

## Quick Start for MCP Use

### Docker (macOS / Linux / Windows with WSL)
1. Install Docker on your workstation.
2. Force an initial build of the Docker image: `echo '{"action":"AUTH_STATUS"}' | ./docker-mcp.sh` (only needed the 
   first time or after a new version!)
3. Run the MCP wrapper from your favorite MCP client: TODO

## Actions

The MCP wrapper (`mcp.py`) supports the following actions:

### `MANIFEST`
Returns the machine-readable capability manifest.
- **Request**: `{"action": "MANIFEST"}`
- **Response**: Standard JSON envelope containing the content of `mcp-manifest.json` in the `data` field.

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
    - `subscription_id` (string, required): The target Azure subscription ID. The wrapper will attempt to 
      select this subscription during the login process or switch to it if already authenticated.
- **Behavior**:
    - If already authenticated, returns current subscription and tenant details.
    - If not authenticated, initiates a device code login flow and returns the `verification_url` and `device_code`. 
    - In a Docker-for-MCP environment, the login process runs in the background for up to 120 seconds to allow for completion and 
      automated subscription selection.
    - In a Docker Compose environment, the azure login waits interactively for the Azure login confirmation.
- **Response**: Standard JSON envelope with `authenticated` status and either account info or device login details.

### `LOGOUT`
Logs out from the current Azure CLI session.
- **Request**: `{"action": "LOGOUT"}`
- **Behavior**: Clears the Azure CLI session and removes the local subscription cache.
- **Response**: Standard JSON envelope with `logged_out: true` or an error if the logout process failed.

### `AUTH_STATUS`
Checks the current authentication status.
- **Request**: `{"action": "AUTH_STATUS"}`
- **Response**: Returns `authenticated: true` with account details or `authenticated: false`.

### `LIST_SUBSCRIPTIONS`
Returns the list of available Azure subscriptions.
- **Request**:
  ```json
  {
    "action": "LIST_SUBSCRIPTIONS",
    "params": {
      "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
  ```
- **Parameters**:
    - `subscription_id` (string, optional): If provided and not authenticated, this subscription will be targeted 
      during the resulting login flow.
- **Behavior**:
    - If already authenticated, returns a cached list of enabled subscriptions.
    - If not authenticated, initiates a device code login flow (same as `LOGIN`).
- **Response**: Standard JSON envelope with a list of subscription objects in `data.subscriptions`.
  Example subscription object:
  ```json
  {
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "name": "My Subscription",
    "tenant_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
    "is_default": true,
    "state": "Enabled"
  }
  ```

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
        "type": "authentication | validation | execution | transport | internal",
        "code": "MACHINE_READABLE_CODE",
        "message": "Human readable message",
        "retryable": true,
        "severity": "low | medium | high | critical",
        "details": { ... }
    },
    "metadata": {
        "timestamp": "ISO-8601",
        "execution_time_ms": 123,
        "authenticated": true,
        "request_id": "uuid",
        "wrapper_version": "1.0.0",
        "protocol_version": "1.0"
    }
}
```

## Error Handling

| Code | Type | Description |
|---|---|---|
| **`AZ_CLI_NOT_FOUND`** | `internal` | Azure CLI is not installed in the environment. |
| **`AZ_NOT_AUTHENTICATED`** | `authentication` | Action requires authentication, but the user is not logged in. |
| **`AZ_LOGIN_FAILED`** | `authentication` | The Azure CLI login process failed to start or provide a device code. |
| **`AZ_LOGOUT_FAILED`** | `authentication` | The logout process failed. |
| **`AZ_TOKEN_EXPIRED`** | `authentication` | The Azure CLI token has expired; re-authentication is required. |
| **`KUSTO_QUERY_FAILED`** | `execution` | The Kusto query execution failed (e.g., syntax error). |
| **`SUBSCRIPTION_CACHE_UNAVAILABLE`** | `internal` | Unable to load subscriptions after login. |
| **`MISSING_REQUIRED_PARAMETER`** | `validation` | A required parameter (like `subscription_id` for `LOGIN`) was not provided. |
| **`MISSING_PARAMS`** | `validation` | Required parameters for `QUERY` were not provided. |
| **`UNKNOWN_ACTION`** | `validation` | The requested action is not recognized by the wrapper. |
| **`JSON_PARSE_ERROR`** | `validation` | The input provided via stdin was not valid JSON. |
| **`WRAPPER_EXCEPTION`** | `internal` | An unexpected internal error occurred. |

## Usage

The MCP wrapper can be run directly via Docker (recommended for full isolation) or native Python.

**Docker (macOS / Linux / Windows with WSL):**
```bash
echo '{"action": "AUTH_STATUS"}' | ./docker-mcp.sh
```

**Docker (Windows Command Prompt):**
```cmd
echo {"action": "AUTH_STATUS"} | docker-mcp.bat
```

**Native Python:**
```bash
echo '{"action": "AUTH_STATUS"}' | python mcp.py
```

> **Note:** Running the MCP wrapper in native Python requires Python 3.12+ AND the Azure CLI on your workstation.


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

