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
| Contracts | `kusto_query_cli/assets/` | Canonical runtime contracts and sample payloads |
| Containers | `docker/` | Image acquisition, runtime mounts, build context |
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
The old root MCP README pointers were removed; the main README links directly
to the task guides. Release and contract guides now live under `docs/`.

CLI adapters call shared services. MCP transport and the one-shot wrapper call
action handlers, which call shared services. Runtime code should not import release
tooling, and transports should not dynamically import command-line entry scripts.
The package name is `kusto_query_cli`; do not create a root `mcp.py` that shadows
the installed MCP SDK.

## Compatibility boundaries

The v2 organization changes implementation ownership and documentation navigation.
It does not mean MCP SDK 3, a new action-envelope version, or a requirement to
change native root Python commands. Explicit image selection is available;
tag-triggered GHCR and GitHub publication is implemented in `scripts/publish_release.py`.

Root native Python launch paths remain stable. Docker shell/Windows launch paths
move as listed below; update client configurations that refer to those host paths.
Commands and entrypoint paths inside container images remain stable. CLI flags, MCP tool names, schemas, envelope
fields, and logical `GET_SCHEMA`/`GET_EXAMPLE` paths remain contracts even if an
implementation module moves.

Keep the application version in `kusto_query_cli/assets/mcp-wrapper-version`, the MCP SDK requirement in
`requirements.txt`, and the action-envelope version in `kusto_query_cli/assets/mcp-protocol-version`
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

## Root layout and path migration

The root contains project identity files, dependency requirements, the requested
release-preparation launcher, and four native Python compatibility launchers.
Implementation, runtime assets, Docker tooling, and detailed documentation belong
in their respective directories. Existing `lib/` imports remain supported.

| Previous checkout path | Current checkout path |
| --- | --- |
| `docker-mcp.sh` / `.bat` | `docker/mcp.sh` / `.bat` |
| `docker-run.sh` / `.bat` | `docker/cli.sh` / `.bat` |
| `docker-mcp-build.sh` / `.bat` | `docker/build.sh` / `.bat` |
| `Dockerfile`, `.dockerignore`, `entrypoint.sh` | `docker/Dockerfile`, `docker/Dockerfile.dockerignore`, `docker/entrypoint.sh` |
| `docker-compose.yml`, `docker-compose.override.yml` | `docker/compose.yaml`, `docker/compose.build.yaml` |
| `.env` | `docker/.env` |
| MCP manifest, capabilities, and version files | `kusto_query_cli/assets/` (same filenames) |
| `schemas/`, `examples/` | `kusto_query_cli/assets/schemas/`, `kusto_query_cli/assets/examples/` |
| `mcp-contract.md` | `docs/reference/action-contract.md` |
| `RELEASING.md` | `docs/development/releases.md` |
| Root MCP README files | `docs/use/mcp.md`, `docs/use/wrapper.md` |

For a native MCP client, keep its existing `mcp-stdio-server.py` command. For a Docker
MCP client, change only the host command path to `docker/mcp.sh` (or `.bat`). Preserve
its arguments and environment. The new Docker launchers can also run the already
published image through `KQC_IMAGE`; Azure state mounts and volume names are unchanged.
Do not remove or recreate volumes as part of this migration. If a local `2.0.0`
image was built before the layout change, run `./docker/build.sh --force` to rebuild
from the updated checkout; a cached image is otherwise reused.

The manifest's schema references and `GET_SCHEMA`/`GET_EXAMPLE` arguments retain
their logical paths relative to the asset directory. Clients do not need to prepend
`kusto_query_cli/assets/` to introspection arguments.
