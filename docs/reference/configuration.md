# Configuration reference

Set environment variables in the process launching the application, or in the MCP
client's per-server environment configuration. A native Python invocation does
not automatically load the `docker/.env` file. Docker MCP launchers read the
logging fields noted below from that file when not already set in the environment.

| Setting | Scope and meaning |
| --- | --- |
| `KQC_IMAGE` | Docker launchers: exact image reference; use cached image or pull if missing, with no build fallback |
| `KUSTO_QUERY_CLI_VERSION` | Local image tag override; does not change application metadata |
| `AZURE_STATE_VOLUME` | Docker MCP named Azure state volume; default `kusto-query-cli-mcp-azure-state` |
| `MCP_CONTAINER_NAME` | Optional Docker MCP container name; unset permits independent concurrent sessions |
| `MCP_AZURE_AUTH_MODE` | Runtime auth policy; MCP Docker launcher sets `container_managed` or `host_shared` |
| `MCP_LOG_LEVEL` | MCP stderr logging: `DEBUG`, `INFO`, `WARNING`, `ERROR`; default `INFO` |
| `MCP_LOG_PAYLOADS` | Include arguments/results at debug level when true; default false |
| `MCP_DEBUG` | One-shot wrapper pretty-printed JSON output when true |
| `KQC_RELEASE_PYTHON` | Python interpreter for the release-preparation launcher |
| `KQC_PYTHON_312`, `KQC_PYTHON_313` | Explicit interpreters for the corresponding release-check matrix rows |

`MCP_LOG_LEVEL` and `MCP_LOG_PAYLOADS` are the Docker MCP launcher's `docker/.env` fallbacks.
Set other selections explicitly in the environment. Release-interpreter details
are in [docs/development/releases.md](../development/releases.md).

MCP launcher options are `--share-host-azure-state` and local-build `--force`.
The CLI Docker launcher accepts leading `--force` for a local rebuild. Image
selection and authentication are independent; setting `KQC_IMAGE` does not select
an Azure identity or change state mounts.

Proxy and subscription caches live in the selected Azure state directory. See
[Authentication](../use/authentication.md) and [Proxy configuration](../use/proxy.md).
Payload logs can contain private query content; inspect logs before sharing them.
