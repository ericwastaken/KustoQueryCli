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
./docker-mcp-build.sh --force
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

or if you will reuse the Azure CLI state from your host

```json
{
  "mcpServers": {
    "kusto-query": {
      "command": "/absolute/path/to/clone/KustoQueryCli/docker-mcp.sh",
      "args": ["--share-host-azure-state"]
    }
  }
}
```

Notes:
- Use the absolute path on your machine. On Windows, use `docker-mcp.bat`.
- The wrapper script will build the image on first run if needed and then start the stdio server with stdio attached (no TTY).
- If you want the container to reuse the Azure CLI state from your host instead of the default named Docker volume, add `--share-host-azure-state` to the wrapper command.
- When using `--share-host-azure-state`, Azure CLI must be installed on the host and you must authenticate on the host first, for example with `az login`, before the MCP container can reuse that state.

## 4) Ask your MCP client to LOGIN, then QUERY

Once your client recognizes the MCP server, you can drive authentication and queries through the exposed tools.

Typical flow in your MCP client chat:

1. Set any PROXY CONFIGURATION needed for your Azure connection (if needed for your setup)
   - "Using the kusto-query MCP server set up SOCKS5 Proxy to host `<host>:<port>` and perform all DNS through the proxy."

2. If you're not sharing Azure State from your Host, ask to log in (device code flow via the Azure CLI inside the MCP container):
   - "Use the kusto-query MCP server and run LOGIN. Guide me through authentication."
   > **Note:** The authentication uses device code flow, so you'll complete it in your browser. After you complete it,
   > return to the MCP client. 

   If you launched the MCP server with `--share-host-azure-state`, do the initial Azure CLI authentication on the host first 
   and then use the MCP server after that host-side login is complete.

   > **Note:** Why share the host azure state? In some scenarios, the access policy for the Azure CLI requires an interactive
   > login. In these cases, the device code login fails by policy restriction. This option allows you to control the Azure CLI
   > state completely interactively on your host before then using it inside the MCP. 

3. Verify auth status: (should show you as logged in if you completed the device code flow on your browser)
   - "Run AUTH_STATUS with the kusto-query MCP server."

4. Run a query:
   - "Using the kusto-query MCP server against my cluster `<cluster-url>` and database `<database name>`, analyze the table 
     `<table name>` and show me `<some interesting question about your data>`."
   - Note that you don't really need to specific a query directly, though you can. But you can also say "analyze the 
     table `<table name>` and help me understand the shape of the data. I am looking for `<some interesting question about your data>`."

What to provide when querying:
- `cluster_url`: e.g., `https://<cluster-name>.<region>.kusto.windows.net`.
- `database`: the ADX database name.
- `query`: your Kusto query text. In an MCP client, you can also just provide a table name and the client will generate 
  a query for you based on some description you provide or even a data question.
- (optional) run `PROXY_CONFIG` first if you want to set or clear a SOCKS5 proxy for the session. That proxy state is 
  persisted in the mounted Azure state volume until cleared.

If your client supports structured tool arguments, it will prompt you for required fields. Otherwise, include them in 
your instruction as plain text and the client will map them to the tool input.

---

Troubleshooting tips:
- If the client cannot find the server, double-check the MCP `command` path.
- To rebuild the image, run `./docker-mcp-build.sh --force` (or `docker-mcp-build.bat --force`).
