# Troubleshooting

| Symptom | Check first |
| --- | --- |
| MCP client cannot start the server | Absolute command path, executable launcher, active Docker daemon, or the correct native virtual-environment interpreter |
| MCP initialization fails | Server stderr; ensure stdio has no banners or other non-protocol output and Docker has no TTY |
| Query is unauthenticated | `AUTH_STATUS`, selected host/container auth mode, and the Azure state mount |
| Login starts but queries still fail | Complete browser instructions, then verify authentication; inspect policy and tenant errors |
| Query uses the wrong account | Host or container Azure CLI account/subscription selection, matching the active state mount |
| Proxy or DNS failures | Proxy address from the container's perspective and whether SOCKS DNS is required |
| Changed code is not running | Selected image reference; force a local rebuild and restart the client session |
| Selected image cannot be pulled | Image reference, registry access, and publication status; there is no automatic local-build fallback |
| Docker CLI cannot read a query file | Local `queries/` mount and the path inside the Linux container |

MCP diagnostics go to stderr. `MCP_LOG_LEVEL=DEBUG` increases detail;
`MCP_LOG_PAYLOADS=true` can additionally expose query arguments/results in debug
logs. Leave payload logging off unless needed and review logs before sharing.
See [Configuration](../reference/configuration.md).

Rebuilding an image does not require removing credential volumes. A tool error is
not an empty successful query result. MCP returns tool data; the one-shot wrapper
returns a status/error/data envelope. Use `MANIFEST`, `GET_SCHEMA`, and
`GET_EXAMPLE` to compare client arguments with the current contract.

For local release-check failures, follow [Release recovery](../development/releases.md#recovery).
