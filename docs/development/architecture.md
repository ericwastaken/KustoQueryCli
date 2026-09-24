# Architecture

Documentation is organized by use case. Implementation is organized by shared
responsibility so native/Docker and human/agent workflows use the same code.

| Layer | Location | Responsibility |
| --- | --- | --- |
| CLI entry points | `k2json.py`, `k2csv.py` | Preserve launch commands and select output format |
| CLI adapter | `kusto_query_cli/cli/runner.py` | Arguments, input selection, CLI behavior |
| MCP entry point | `mcp-stdio-server.py` | Start the long-running stdio server |
| MCP transport | `kusto_query_cli/mcp/server.py` | Tool listing, schema validation, dispatch, protocol results |
| Action handlers | `kusto_query_cli/mcp/actions.py` | Query, auth, proxy, and manifest actions |
| Envelope adapter | `kusto_query_cli/mcp/wrapper.py`, `envelopes.py` | One-shot input and response contract |
| Shared services | `kusto_query_cli/core/` | ADX query execution, Azure auth, proxy state, serialization |
| Resource lookup | `kusto_query_cli/resources.py` | Resolve canonical repository metadata and contracts |
| Compatibility modules | `lib/` and root Python scripts | Preserve historical imports and launch paths |
| Contracts | `schemas/`, `examples/`, manifest and protocol files | Canonical runtime contracts and sample payloads |
| Containers | Root Dockerfile and launchers, `scripts/docker/` | Image acquisition, runtime mounts, build context |
| Release tooling | `scripts/release.py`, `release_checks.py`, `release-matrix.json` | Preparation and shared local/CI validation |

## Previous and current locations

| Previously | Implementation now |
| --- | --- |
| `lib/k2run.py` | `kusto_query_cli/cli/runner.py` |
| `lib/KustoHandler.py` | `kusto_query_cli/core/query.py` |
| `lib/AzureCliHelper.py` | `kusto_query_cli/core/auth.py` |
| Auth, proxy, and serialization mixed into `mcp-wrapper.py` | Dedicated modules under `kusto_query_cli/core/` |
| Action dispatch and envelopes mixed into `mcp-wrapper.py` | `kusto_query_cli/mcp/actions.py`, `envelopes.py`, and `wrapper.py` |
| `mcp-stdio-server.py` implementation | `kusto_query_cli/mcp/server.py` |
| Automated `tests/test_*.py` | `tests/unit/` |
| `tests/mcp_smoke.py` | `tests/integration/mcp_smoke.py` |
| Hyphenated live integration scripts under `tests/` | `tests/manual/` |
| Long root README and MCP guides | `docs/use/`, `docs/containers/`, `docs/development/`, `docs/reference/` |

Historical root Python scripts and `lib/` modules remain compatibility adapters.
Root MCP README files remain navigation pointers. Test helper paths have moved;
update personal commands to use the paths above. Root `RELEASING.md` and
`mcp-contract.md` remain canonical.

CLI adapters call shared services. MCP transport and the one-shot wrapper call
action handlers, which call shared services. Runtime code should not import release
tooling, and transports should not dynamically import command-line entry scripts.
The package name is `kusto_query_cli`; do not create a root `mcp.py` that shadows
the installed MCP SDK.

## Compatibility boundaries

The v2 organization changes implementation ownership and documentation navigation.
It does not mean MCP SDK 3, a new action-envelope version, or a requirement to
change existing root launcher commands. Explicit image selection is available;
tag-triggered GHCR and GitHub publication is implemented in `scripts/publish_release.py`.

Root Python and shell/Windows launch paths remain stable because client settings,
containers, and scripts refer to them. CLI flags, MCP tool names, schemas, envelope
fields, and logical `GET_SCHEMA`/`GET_EXAMPLE` paths remain contracts even if an
implementation module moves.

Keep the application version in `mcp-wrapper-version`, the MCP SDK requirement in
`requirements.txt`, and the action-envelope version in `mcp-protocol-version`
distinct. The envelope version is not the negotiated MCP wire protocol version.
Resource lookup fails if required version files are absent instead of inventing
fallback application/protocol values. Include canonical resources in deployments.

CLI and MCP share query mechanisms but have distinct adapters and state policies.
CLI proxy flags configure a process; MCP proxy configuration persists in Azure
state. Docker CLI and MCP keep their existing separate default auth volumes.

## Resource and build changes

Schemas and examples are runtime resources, not expendable documentation. Resource
moves must update lookup code, Docker's allowlist, metadata checks, tests, and any
manifest references together. Preserve canonical sources instead of maintaining
hand-edited copies for native and Docker execution.
