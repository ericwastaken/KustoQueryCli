# Kusto Query CLI — MCP STDIO Server

This repository includes an MCP stdio server implementation that exposes Kusto (ADX) capabilities to AI clients over the 
Model Context Protocol.

> Quickstart: If you just want to get running fast with Docker and an MCP client, see [README-MCP-QUICKSTART.md](README-MCP-QUICKSTART.md).

## What this server provides

- A lightweight stdio server (`mcp-stdio-server.py`) built on the official Python MCP SDK
- A set of tools mapped to atomic actions implemented by the wrapper:
  - `AUTH_STATUS`, `LOGIN`, `LOGOUT`, `LIST_SUBSCRIPTIONS`, `PROXY_CONFIG`, `QUERY`, and `MANIFEST`
- Dynamic tool input schemas loaded from the repository’s canonical JSON Schemas under `schemas/`
- Introspection utilities so clients can fetch the authoritative artifacts directly:
  - `GET_SCHEMA` — returns any JSON Schema under `schemas/`
  - `GET_EXAMPLE` — returns any example payload under `examples/`

By sourcing definitions from `SCHEMAS` and sample payloads from `EXAMPLES`, the server avoids duplicating documentation 
and ensures a single source of truth for clients.

## How to run

The recommended way is to let your MCP client spawn the Docker wrapper script:

```json
{
  "kusto-query": {
    "command": "/absolute/path/to/KustoQueryCli/docker-mcp.sh"
  }
}
```

Notes:
- The Docker wrapper runs `python mcp-stdio-server.py` with stdio attached (no TTY) to preserve MCP framing.
- The image is built automatically on first run based on `mcp-wrapper-version`, which is the canonical wrapper version file. You can still override the Docker tag explicitly by setting `KUSTO_QUERY_CLI_VERSION` in the environment.
- Optional `MCP_CONTAINER_NAME`: set this env var if you want a predictable Docker container name (e.g., for easier `docker logs` or manual inspection). By default it is omitted so Docker assigns a random name, allowing multiple concurrent MCP containers without conflict. Containers are started with `--rm` and auto-remove when they stop.
- Shared Azure CLI state via `AZURE_STATE_VOLUME`: by default the wrapper mounts a persistent Docker volume `kusto-query-cli-mcp-azure-state` at `/root/.azure`. This lets multiple containers (and successive runs) share Azure CLI credentials/state, so you don’t need to re-authenticate on every run. You can override it, for example:
    - Bash: `AZURE_STATE_VOLUME=my-azure-state ./docker-mcp.sh`
    - Windows: `set AZURE_STATE_VOLUME=my-azure-state && docker-mcp.bat`
    - To isolate credentials per container, set a unique volume per instance (or point to an empty one).
- Optional `--share-host-azure-state`: instead of the named Docker volume, mount your host Azure CLI state into the container at `/root/.azure`.
    - Bash/macOS/Linux: `./docker-mcp.sh --share-host-azure-state`
    - Windows CMD: `docker-mcp.bat --share-host-azure-state`
    - This uses your host Azure CLI directory directly:
      - macOS/Linux: `$HOME/.azure`
      - Windows CMD: `%USERPROFILE%\.azure`
    - Requirement: when using `--share-host-azure-state`, Azure CLI must already be installed on the host, and you must complete authentication on the host first, for example with `az login`, before expecting the MCP container to reuse that state.
    - In this mode, the MCP `LOGIN` and `LOGOUT` tools do not initiate authentication inside the container. They instead report that auth is host-managed and direct you to run `az login`, `az account set --subscription <subscription-id>`, or `az logout` on the host. `AUTH_STATUS` reports whether auth is `container_managed` or `host_shared`.

### Build helper and force rebuilds

- Build-only helper scripts:
  - Bash/macOS/Linux: `./docker-mcp-build.sh`
  - Windows CMD: `docker-mcp-build.bat`
- These scripts resolve the image version in this order: `KUSTO_QUERY_CLI_VERSION` env var > `mcp-wrapper-version` file > `dev`.
- On success, they print the resolved Docker image tag (e.g., `kusto-query-cli:0.3.1`) to stdout so other scripts can consume it.

Force rebuild flag:

- Pass `--force` to either the build helper or the wrapper scripts to rebuild the image even if it already exists:

  - Bash/macOS/Linux:
    - Build only: `./docker-mcp-build.sh --force`
    - Run via wrapper: `./docker-mcp.sh --force`
  - Windows CMD:
    - Build only: `docker-mcp-build.bat --force`
    - Run via wrapper: `docker-mcp.bat --force`

- What `--force` does:
  - Removes the existing image for the resolved version tag (if present) and then rebuilds it.
  - All status messages are written to stderr; only the final image tag is written to stdout by the build helpers.
  - Any additional arguments you pass alongside `--force` to the wrapper scripts are forwarded to `python mcp-stdio-server.py` as usual.

For local testing without Docker:

```bash
python mcp-stdio-server.py
```

You can also use the helper scripts under `tests/` to exercise `initialize`, `tools/list`, and `tools/call` flows.

## Protocol contract and manifest

- Protocol notes: see [`mcp-contract.md`](mcp-contract.md)
- Server capability manifest: [`mcp-manifest.json`](mcp-manifest.json)
- Supported protocol version recorded in: [`mcp-protocol-version`](mcp-protocol-version)

## Schemas and examples (single source of truth)

- Action request/response schemas: `schemas/actions/*.schema.json`
- Global envelope and manifest schemas: `schemas/*.schema.json`
- Example payloads for requests/responses: `examples/*.json`

The stdio server loads each tool’s `inputSchema` from the action’s canonical request schema by extracting its `params` 
definition, and references available examples in tool descriptions. Use the introspection tools to fetch exact files at 
runtime:

- `GET_SCHEMA { path: "actions/QUERY.request.schema.json" }`
- `GET_EXAMPLE { name: "QUERY.request.json" }`

## Logging and diagnostics

The stdio server now emits structured logs to stderr so they do not interfere with the MCP stdio protocol on stdout. You can control verbosity via environment variables:

- `MCP_LOG_LEVEL`: one of `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`).
- `MCP_LOG_PAYLOADS`: when set to `true`, includes sanitized tool arguments and results at `DEBUG` level (defaults to `false`).

Examples:

These environment variables can be set in a `.env` file in the repository root:

```bash
# .env file example
MCP_LOG_LEVEL=DEBUG
MCP_LOG_PAYLOADS=true
MCP_CONTAINER_NAME=kqc-mcp
```

Then run the server:

```bash
# Local run (automatically loads .env if present)
python mcp-stdio-server.py

# Docker wrapper (automatically loads .env if present)
./docker-mcp.sh
```

What gets logged:

- **INFO level:**
  - Server startup: versions (server, Python, protocol) and readiness.
  - Tool calls: request received (tool name only), action start, success/failure, and duration in ms.
  - Introspection access: requested schema/example file names.
- **DEBUG level:**
  - All INFO-level messages plus:
  - Detailed tool arguments (sanitized) when `MCP_LOG_PAYLOADS=true`.
  - Full action results/responses (sanitized) when `MCP_LOG_PAYLOADS=true`.
  - Internal protocol events and state transitions.

**About `MCP_LOG_PAYLOADS=true`:**

- When enabled, the server includes sanitized tool call arguments and results in DEBUG logs.
- Sensitive fields (e.g., credentials, tokens) are automatically redacted.
- This is useful for troubleshooting request/response flows without exposing secrets.
- Defaults to `false` to avoid logging large or sensitive payloads unless explicitly needed.

## Wrapper implementation details

The stdio server delegates atomic action execution to the MCP wrapper module. For a deeper, action-by-action description 
(authentication flows, query parameters, error envelopes), see:

- [`README-MCP-WRAPPER.md`](README-MCP-WRAPPER.md)
