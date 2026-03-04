# Kusto Query CLI — MCP STDIO Server

This repository includes an MCP stdio server implementation that exposes Kusto (ADX) capabilities to AI clients over the 
Model Context Protocol.

## What this server provides

- A lightweight stdio server (`mcp-stdio-server.py`) built on the official Python MCP SDK
- A set of tools mapped to atomic actions implemented by the wrapper:
  - `AUTH_STATUS`, `LOGIN`, `LOGOUT`, `LIST_SUBSCRIPTIONS`, `QUERY`, and `MANIFEST`
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
- The image is built automatically on first run based on `mcp-wrapper-version` unless you pin `KUSTO_QUERY_CLI_VERSION`.

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

## Wrapper implementation details

The stdio server delegates atomic action execution to the MCP wrapper module. For a deeper, action-by-action description 
(authentication flows, query parameters, error envelopes), see:

- [`README-MCP-WRAPPER.md`](README-MCP-WRAPPER.md)


