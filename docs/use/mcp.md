# Use MCP

Choose native Python or Docker below. Both expose the same tools over stdio.
MCP clients start the process and handle protocol initialization; do not type
wrapper action envelopes directly into the server's stdin.

## Docker

Clone the repository and start Docker:

```bash
git clone https://github.com/ericwastaken/KustoQueryCli.git
cd KustoQueryCli
./docker-mcp-build.sh
```

The build step is optional: the launcher builds the local image if it is absent.
For an explicit image instead, see [Use a container image](../containers/use-image.md).
Set `KQC_IMAGE=ghcr.io/ericwastaken/kustoquerycli:2.0.0` to use the released image.

For a client using an `mcpServers` configuration, merge this entry into its existing
configuration. Replace the path with your actual checkout location:

```json
{
    "mcpServers": {
        "kusto-query": {
            "command": "/absolute/path/to/KustoQueryCli/docker-mcp.sh"
        }
    }
}
```

Default authentication uses persistent container-managed Azure state. To reuse a
host Azure CLI login, authenticate on the host with `az login` and add
`"args": ["--share-host-azure-state"]` to the server entry. See
[Authentication](authentication.md) for the differences.

Windows CMD launchers are also provided: `docker-mcp-build.bat` and
`docker-mcp.bat`. Configure the client to invoke the launcher according to that
client's Windows command rules. Use absolute paths and escape backslashes in JSON.

## Native Python

From a clone, create the environment described in [Native setup](cli.md#native-python).
Install Azure CLI and authenticate with `az login`. Configure the MCP client with
the environment's Python and the absolute server path:

```json
{
    "mcpServers": {
        "kusto-query": {
            "command": "/absolute/path/to/KustoQueryCli/venv/bin/python",
            "args": ["/absolute/path/to/KustoQueryCli/mcp-stdio-server.py"],
            "env": {
                "MCP_AZURE_AUTH_MODE": "host_shared"
            }
        }
    }
}
```

On Windows, use the interpreter in the environment's `Scripts` directory. The
Python process uses that operating-system user's Azure state. The example selects
`host_shared` policy so MCP LOGIN/LOGOUT direct you to host Azure CLI commands.
Without that setting, the default policy permits the native process to manage
login/logout in its Azure state directory. Use the intended account and policy
when starting the client.

## First query

1. Have the client discover tools. If a proxy is required, configure it with
    `PROXY_CONFIG` as described in [Proxy configuration](proxy.md).
2. Call `AUTH_STATUS`. If a container-managed session needs authentication, call
    `LOGIN`, complete the returned browser/device-code steps, and call
    `AUTH_STATUS` again. For host-shared authentication, follow the tool's host
    login instructions instead.
3. Supply your cluster URL, database, and query or the question you want answered.
    A client can generate KQL from your question, but still needs the correct
    cluster and database. A bounded first query is a useful connection check.

The `QUERY` tool takes direct arguments:

```json
{
    "cluster_url": "https://<cluster>.<region>.kusto.windows.net",
    "database": "<database>",
    "query": "<table> | take 10"
}
```

Replace placeholders with actual values. The MCP client supplies the tool name
separately. The `action`/`params` envelope belongs to the [wrapper](wrapper.md).

Inspect the tool's error status before treating the result as data. Use `MANIFEST`,
`GET_SCHEMA`, and `GET_EXAMPLE` to inspect the contract. See the
[MCP reference](../reference/mcp.md) for all tools.

After changing local code, rebuild using `./docker-mcp-build.sh --force` and restart
the MCP session. MCP stdout is protocol-only; diagnostics appear on stderr.
