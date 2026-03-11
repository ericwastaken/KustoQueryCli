# Kusto Query CLI - MCP Wrapper

This project provides a Model Context Protocol (MCP) wrapper for interacting with Azure Data Explorer (ADX) via the Azure CLI.

## Quick Start for MCP Use

### Run as an MCP stdio server (recommended for MCP clients)
- This project includes a minimal MCP stdio server implemented with the official Python SDK: `mcp-stdio-server.py`.
- MCP clients should spawn the Docker wrapper script directly as the server command (stdio transport):

Example client configuration:

```json
{
  "kusto-query": {
    "command": "/absolute/path/to/KustoQueryCli/docker-mcp.sh"
  }
}
```

Notes:
- The Docker wrapper uses `--interactive` only (no TTY) to preserve MCP stdio framing.
- It will automatically build the image on first run. You can optionally set `KUSTO_QUERY_CLI_VERSION` in your environment 
  or `.env`; otherwise it falls back to the value in `mcp-wrapper-version`.

### Docker (macOS / Linux / Windows with WSL)
1. Install Docker on your workstation.
2. Force an initial build of the Docker image: `echo '{"action":"AUTH_STATUS"}' | ./docker-mcp.sh` (only needed the 
   first time or after a new version!)
3. Run the MCP wrapper from your favorite MCP client using the configuration above.

## Actions

The MCP wrapper (`mcp-wrapper.py`) supports the following actions:

### `MANIFEST`
Returns the machine-readable capability manifest.
- Request: `{"action": "MANIFEST"}`
- Response: Standard JSON envelope containing the content of `mcp-manifest.json` in the `data` field.

### `LOGIN`
Initiates or verifies Azure CLI authentication.
- Request: 
  ```json
  {
    "action": "LOGIN",
    "params": {
      "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
  ```
- Parameters:
    - `subscription_id` (string, optional): The target Azure subscription ID. The wrapper will attempt to 
      select this subscription during the login process or switch to it if already authenticated.
- Behavior:
    - If already authenticated, returns current subscription and tenant details.
    - If not authenticated, initiates a device code login flow and returns the `verification_url` and `device_code`. 
    - In a Docker-for-MCP environment, the login process runs in the background for up to 120 seconds to allow for completion and 
      automated subscription selection.
    - In a Docker Compose environment, the azure login waits interactively for the Azure login confirmation.
- Response: Standard JSON envelope with `authenticated` status and either account info or device login details.

### `LOGOUT`
Logs out from the current Azure CLI session.
- Request: `{"action": "LOGOUT"}`
- Behavior: Clears the Azure CLI session and removes the local subscription cache.
- Response: Standard JSON envelope with `logged_out: true` or an error if the logout process failed.

### `AUTH_STATUS`
Checks the current authentication status.
- Request: `{"action": "AUTH_STATUS"}`
- Response: Returns `authenticated: true` with account details or `authenticated: false`.

### `LIST_SUBSCRIPTIONS`
Returns the list of available Azure subscriptions.
- Request:
  ```json
  {
    "action": "LIST_SUBSCRIPTIONS",
    "params": {
      "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
  ```
- Parameters:
    - `subscription_id` (string, optional): If provided and not authenticated, this subscription will be targeted 
      during the resulting login flow.
- Behavior:
    - If already authenticated, returns a cached list of enabled subscriptions.
    - If not authenticated, initiates a device code login flow (same as `LOGIN`).
- Response: Standard JSON envelope with a list of subscription objects in `data.subscriptions`.

### `QUERY`
Executes a Kusto query against a specific cluster and database.
- Request:
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
- Parameters:
    - `query` (string, required): The KQL query to execute.
    - `database` (string, required): The target database name.
    - `cluster_url` (string, required): The ADX cluster URL.
    - `socks5_proxy` (string, optional): SOCKS5 proxy in `host:port` format.
    - `socks5_dns` (boolean|string|integer, optional): Whether to use proxy for DNS (defaults to `false`). Accepts:
      - Booleans: `true` / `false`
      - Integers: `1` / `0`
      - Strings: `"true"`, `"false"`, `"yes"`, `"no"`, `"on"`, `"off"` (case-insensitive)
- Response: Standard JSON envelope containing a list of objects (rows) in the `data.result` field.

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

## Usage for Testing

The MCP wrapper can be run directly in native Python, though this should be used for testing only.
For proper MCP use, see the [Quick Start](#quick-start-for-mcp-use) section above.

Native Python:
```bash
echo '{"action": "AUTH_STATUS"}' | python mcp-wrapper.py
```

> Note: Running the MCP wrapper in native Python requires Python 3.12+ AND the Azure CLI on your workstation.


## Environment Variables

- `MCP_DEBUG`: Set to `true` to enable pretty-printed JSON and include detailed error messages.

Example: Enabling Debug Mode

To run the MCP wrapper with debug mode enabled on macOS/Linux:

```bash
export MCP_DEBUG=true
echo '{"action": "AUTH_STATUS"}' | python mcp-wrapper.py
```

On Windows:

```cmd
set MCP_DEBUG=true
echo {"action": "AUTH_STATUS"} | python mcp-wrapper.py
```
