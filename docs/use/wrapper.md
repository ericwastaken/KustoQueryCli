# Use the one-shot wrapper

The wrapper reads one JSON action envelope from stdin, performs the action, writes
a JSON response envelope, and exits. Use it for scripts that want the action
contract without an MCP client. For a long-running MCP connection, use
[Use MCP](mcp.md).

Complete [Native setup](cli.md#native-python), then run from the repository root:

```bash
printf '%s\n' '{"action":"AUTH_STATUS"}' | python mcp-wrapper.py
printf '%s\n' '{"action":"MANIFEST"}' | python mcp-wrapper.py
```

A query envelope looks like this, with placeholders replaced:

```json
{
    "action": "QUERY",
    "params": {
        "cluster_url": "https://<cluster>.<region>.kusto.windows.net",
        "database": "<database>",
        "query": "<table> | take 10"
    }
}
```

Save the envelope to a file and use `python mcp-wrapper.py < request.json`.
For Docker, the same Python entry point exists in the application image; use
`docker run --rm -i` with the selected image and the intended Azure state mount.
The wrapper does not implement MCP initialization or JSON-RPC framing.

Supported actions are `MANIFEST`, `AUTH_STATUS`, `LOGIN`, `LOGOUT`,
`LIST_SUBSCRIPTIONS`, `PROXY_CONFIG`, and `QUERY`. `GET_SCHEMA` and `GET_EXAMPLE`
are MCP server tools, not wrapper actions. Canonical wrapper examples are in
[examples/](../../examples/); schemas are in [schemas/](../../schemas/).

Inspect response `status` and error details before using `data`. The response
includes application/protocol metadata; see [mcp-contract.md](../../mcp-contract.md).
Authentication and persistent proxy changes follow the shared
[authentication](authentication.md) and [proxy](proxy.md) guidance.
