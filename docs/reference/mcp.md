# MCP tools and contracts

The long-running MCP stdio server and one-shot wrapper share action handlers.
They have different inputs: MCP tools receive direct argument objects; the wrapper
receives an `action` and optional `params` envelope. Canonical request schemas
include the envelope; the MCP adapter extracts their `params` schema.

| MCP tool | Purpose |
| --- | --- |
| `AUTH_STATUS` | Inspect authentication and selected auth mode |
| `LOGIN` | Start/verify login or direct host-managed authentication |
| `LOGOUT` | Intentionally sign out or direct host-managed logout |
| `LIST_SUBSCRIPTIONS` | Inspect available subscriptions; unauthenticated flows may initiate login |
| `PROXY_CONFIG` | Inspect, set, or clear persisted SOCKS configuration |
| `QUERY` | Query a specified cluster and database |
| `MANIFEST` | Discover application and action metadata |
| `GET_SCHEMA` | Read a canonical schema by relative path |
| `GET_EXAMPLE` | Read a canonical example by filename |

`GET_SCHEMA` and `GET_EXAMPLE` are server introspection tools, not one-shot wrapper
actions. For example, call `GET_SCHEMA` with
`{"path":"actions/QUERY.request.schema.json"}` or `GET_EXAMPLE` with
`{"name":"QUERY.request.json"}`. Logical names stay stable across source moves.

The sources of truth are [schemas/](../../schemas/), [examples/](../../examples/),
[mcp-manifest.json](../../mcp-manifest.json), and
[mcp-contract.md](../../mcp-contract.md). The manifest lists wrapper actions;
tool discovery also includes the server's introspection tools.

## Results and versions

Check MCP tool-error status before treating a response as query data. Normal MCP
tool results unwrap the internal action envelope and return its data, such as
query results and row count, as structured content plus matching JSON text for
older clients. The one-shot wrapper retains the full `status`/`error`/`data`
envelope. The server validates tool arguments against JSON Schema.

The application release is recorded in
[mcp-wrapper-version](../../mcp-wrapper-version). The server dependency uses MCP
SDK 2.x as bounded in [requirements.txt](../../requirements.txt), with modern and
legacy client compatibility checked by the test matrix.
[mcp-protocol-version](../../mcp-protocol-version) describes this project's action
envelope; it is not the SDK major version or MCP wire protocol revision.

See [Use MCP](../use/mcp.md), [Use the wrapper](../use/wrapper.md), and
[Configuration](configuration.md).
