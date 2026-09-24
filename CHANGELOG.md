# Changelog

## 1.2.1

- Limit the MCP Python SDK to `mcp>=1.26.0,<2` for the existing stdio server.
    MCP 2 removed the handler decorators this server uses, causing fresh
    installations of 1.2.0 to fail at startup when they resolve MCP 2.x.
- Update the application version and default Docker image tag to 1.2.1 so the
    launch helpers build a fresh image containing the dependency constraint.

### Updating from 1.2.0

Install this release and run `pip install -r requirements.txt` in your virtual
environment. This also downgrades an incompatible MCP 2.x installation.

Docker users can run `./docker-mcp-build.sh --force` on macOS/Linux or
`docker-mcp-build.bat --force` on Windows. If you explicitly set
`KUSTO_QUERY_CLI_VERSION`, update it to `1.2.1` as well. Azure CLI state remains
in the existing mounted volume or host directory.

MCP 2 support will be handled in a separate migration. The original `v1.2.0`
release tag is unchanged.
