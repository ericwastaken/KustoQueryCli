# Agent instructions

These instructions apply throughout the repository. Choose guidance by the user's
task: using the application does not require changing it or preparing a release.

## Task routing

| Task | Read |
| --- | --- |
| Consume MCP natively or in Docker | [Use MCP](docs/use/mcp.md), [MCP reference](docs/reference/mcp.md) |
| Consume CLI natively or in Docker | [Use the CLI](docs/use/cli.md), [CLI reference](docs/reference/cli.md) |
| Use the one-shot wrapper | [Wrapper](docs/use/wrapper.md) |
| Choose or build an image | [Image selection](docs/containers/use-image.md), [local builds](docs/containers/build-image.md) |
| Change Python or MCP behavior | [Setup](docs/development/setup.md), [architecture](docs/development/architecture.md), [Python development](docs/development/python.md) |
| Change Docker builds or launchers | [Container development](docs/development/containers.md) |
| Validate changes | [Testing](docs/development/testing.md) |
| Prepare a requested release | [docs/development/releases.md](docs/development/releases.md) |

Use these canonical guides rather than duplicating instructions in new agent-only
how-to documents. Human and agent developers use the same implementation and checks.

## Working conventions

- Inspect `git status` and relevant code before editing. Preserve unrelated edits,
    scratch files, credentials, and caches. Never reset or clean the checkout just
    to make checks pass.
- Prefer macOS/Linux, Python, and Bash; look for tools under `/opt/homebrew/` on
    macOS. Shell launchers must remain compatible with Bash 3.2.
- Match code style. Use four spaces for Markdown indentation and two blank lines
    above Python function and method definitions. Avoid decorative Unicode and
    em dashes.
- Keep review work unpublished unless the user authorizes committing, pushing, or
    releasing. Use `codex/` for new branches unless another name is requested.
- Report changes, relevant validation, and unavailable checks. Link files for
    review; do not launch desktop editors unless asked.

## Development invariants

- Keep native root Python launchers and compatibility imports stable. Docker
    launchers live under `docker/`; document path migrations in the architecture guide.
    Put behavior in `kusto_query_cli`; use ordinary imports instead of loading executable scripts.
- Reserve MCP stdout for protocol messages. Diagnostics go to stderr; Docker MCP
    uses `-i` without `-t`.
- Preserve explicit JSON Schema validation and tool-error results. Successful
    structured MCP results need matching JSON text for legacy clients.
- Update contracts, examples, handlers, and documentation together. Schemas and
    examples are runtime resources. Account for Docker's allowlisted context.
- Preserve auth modes, existing Azure-state volume names, and persistent proxy
    semantics. Keep Windows `.bat` launchers consistent with shared behavior.
- Select relevant tests from the testing guide. Shared local/CI checks and matrix
    are authoritative; do not create a second implementation in a workflow.
- Read release guidance before version changes. Application, action-envelope, and
    MCP SDK versions are distinct. Never move an existing release tag.
- `build-for-release.sh` prepares metadata and validates; it does not commit, tag,
    push, or publish. Version tags trigger the release workflow. Registry/network errors
    mean availability is unknown, not that a version is free.

## Consumer invariants

- Use MCP tool arguments directly; reserve `action`/`params` envelopes for the
    one-shot wrapper. Discover details with `MANIFEST`, `GET_SCHEMA`, and `GET_EXAMPLE`.
- Obtain the actual cluster URL and database from the user's request/configuration;
    never treat example endpoints as their target. Start exploration with bounded,
    read-only queries and expand according to the task.
- Check `AUTH_STATUS`. Starting login does not mean it succeeded; let the user
    complete browser instructions and verify. In host-shared mode, follow host
    Azure CLI instructions rather than logging in/out inside the container.
- Inspect MCP tool-error status and returned data; for the one-shot wrapper,
    inspect envelope status/error/data. Never present an error as an empty
    successful query. Use logout or proxy clearing only when the workflow calls for it.
- Proxy configuration persists across calls and sessions sharing Azure state.
    Do not delete auth volumes as routine troubleshooting.
- Keep credentials, device codes, and private query data out of committed examples
    and shared logs. Prefer mocked regressions to real credential operations.
