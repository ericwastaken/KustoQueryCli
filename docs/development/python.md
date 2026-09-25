# Change Python behavior

Start with [Setup](setup.md) and the [Architecture map](architecture.md). Keep the
root launchers thin; edit the responsible package module instead.

| Change | Start in | Validate |
| --- | --- | --- |
| CLI flags, input precedence, JSON/CSV behavior | `kusto_query_cli/cli/runner.py` and CLI entry points | CLI regressions, root launcher behavior |
| ADX execution or accepted query arguments | `kusto_query_cli/core/query.py` | Mocked query regressions and affected adapters |
| Login, auth mode, subscription state | `kusto_query_cli/core/auth.py` and MCP actions | Mocked auth/state regressions |
| Proxy behavior | `kusto_query_cli/core/proxy.py`, query service, and actions | Persist/load/clear behavior and environment restoration |
| JSON representation | `kusto_query_cli/core/serialization.py` | Dates, UUIDs, pandas/NumPy values, and envelope results |
| MCP tools and action behavior | `kusto_query_cli/mcp/` and `kusto_query_cli/assets/schemas/` | Schema validation, tool results, modern/legacy smoke tests |

Match existing style, leave two blank lines above Python function and method
definitions, and use ordinary imports from `kusto_query_cli`. Shared services
should return data or errors; adapters decide how to present CLI output, wrapper
envelopes, or MCP responses.

## MCP contract rules

- Reserve stdout for protocol messages and send diagnostics to stderr.
- Preserve explicit tool-argument JSON Schema validation in the low-level MCP
    adapter. Do not assume the SDK performs that application validation.
- Return tool failures as error results. Successful structured results also need
    matching JSON text content for legacy clients.
- Update schemas, examples, handlers, and references together for action changes.
    Preserve logical introspection paths.
- Preserve host-shared LOGIN/LOGOUT behavior and persistent proxy semantics.
- Keep application, envelope-protocol, and dependency versions separate.

Run appropriate [tests](testing.md). Tests should use temporary Azure state and
mock auth/query operations. Live Azure login or queries are separate, intentional
integration work, not a substitute for deterministic regression coverage.
