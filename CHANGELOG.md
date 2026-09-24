# Changelog

## 2.0.0

- Reorganize documentation around MCP, CLI, container consumption, development, and release tasks.
- Extract shared Python services and separate CLI, MCP transport, and one-shot adapters into `kusto_query_cli`.
- Preserve root launch commands and legacy `lib` imports while moving implementation into the package.
- Separate explicit container image selection from local builds, retaining authentication modes and state volumes.
- Share local and CI release validation, with interactive version selection and conflict checks.
- Separate automated unit/protocol checks from manual Azure integration helpers.
- Return validation envelopes for malformed one-shot requests instead of exiting without a response.

- Publish tested Linux AMD64 and ARM64 images to GHCR with matching GitHub releases and digest manifests.

## 1.3.0

- Support MCP Python SDK 2.2 and newer 2.x releases (`mcp>=2.2.0,<3`).
- Migrate low-level handler registration and explicit result construction while
    preserving tool names, schemas, structured JSON results, and readable errors.
- Explicitly validate tool arguments before invoking Azure or Kusto operations.
- Support both modern MCP discovery and legacy initialization over stdio.
- Add adapter regression tests and stdio smoke checks for modern and older clients.
- Fix fallback query-value serialization so UUID values are strings instead of null.

Upgrade native environments with `pip install -r requirements.txt`. Docker users
should build the new `1.3.0` image using `./docker-mcp-build.sh` or
`docker-mcp-build.bat`. Update an explicit `KUSTO_QUERY_CLI_VERSION` override to
`1.3.0`. Existing MCP client commands and Azure state mounts continue to work.

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
