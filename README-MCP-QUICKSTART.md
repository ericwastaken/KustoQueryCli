# MCP Server Quickstart

This quickstart shows how to:
- Clone the repo
- Build the Docker image for the MCP stdio server
- Point your MCP client to the wrapper command
- Ask your MCP client to LOGIN and then QUERY

Nothing else is covered here. For full details, see `README-MCP-SERVER.md` and `README-MCP-WRAPPER.md`.

## 1) Clone the repository

```bash
git clone https://github.com/ericwastaken/KustoQueryCli.git
cd KustoQueryCli
```

## 2) Build the Docker image (one-time or as needed)

Use the helper script for your platform. It resolves the correct image tag and builds it.

- macOS/Linux:
```bash
./docker-mcp-build.sh
```

- Windows (CMD):
```bat
docker-mcp-build.bat
```

Optional: force a rebuild any time by adding `--force`.

## 3) Point your MCP client at the wrapper command

Configure your MCP client to run the stdio server via the Docker wrapper script. Use an absolute path to `docker-mcp.sh` 
(or `docker-mcp.bat` on Windows).

### Example: Claude Desktop config

Add or merge this into your Claude Desktop config (showing only the `mcpServers` section and omitting unrelated keys):

```json
{
  "mcpServers": {
    
    "kusto-query": {
      "command": "/absolute/path/to/clone/KustoQueryCli/docker-mcp.sh"
    }

  }
}
```

Notes:
- Use the absolute path on your machine. On Windows, use `docker-mcp.bat`.
- The wrapper script will build the image on first run if needed and then start the stdio server with stdio attached (no TTY).

## 4) Ask your MCP client to LOGIN, then QUERY

Once your client recognizes the MCP server, you can drive authentication and queries through the exposed tools.

Typical flow in your MCP client chat:

1. Ask to log in (device code flow via Azure CLI if needed):
   - "Use the kusto-query MCP server and run LOGIN. Guide me through authentication."
   > **Note:** The authentication uses device code flow, so you'll complete it in your browser. After you complete it,
   > return to the MCP client. 

2. Verify auth status: (should show you as logged in if you completed the device code flow on your browser)
   - "Run AUTH_STATUS with the kusto-query MCP server."

3. Run a query:
   - "Using the kusto-query MCP server, call QUERY against my cluster and database with this KQL: ..."

What to provide when querying:
- `cluster`: e.g., `https://<cluster-name>.<region>.kusto.windows.net`.
- `database`: the ADX database name.
- `kql`: your Kusto query text.
- (optional) `socks5_proxy`: if you need to use a SOCKS5 proxy for the query, enter it as `<host>:<port>`.
- (optional) `socks5_dns`: if you are using a SOCKS5 proxy for the query, enter `true|false` to control whether DNS 
  resolution is done through the proxy.

If your client supports structured tool arguments, it will prompt you for required fields. Otherwise, include them in 
your instruction as plain text and the client will map them to the tool input.

---

Troubleshooting tips:
- If the client cannot find the server, double-check the absolute `command` path.
- To rebuild the image, run `./docker-mcp-build.sh --force` (or `docker-mcp-build.bat --force`).
