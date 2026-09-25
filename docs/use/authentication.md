# Authentication and Azure state

All interfaces use Azure CLI credentials to access ADX. Use an account authorized
for the target cluster and database. An Azure subscription listing does not
identify the cluster URL or database for a query.

| Mode | Credentials and state | How to authenticate |
| --- | --- | --- |
| Native CLI | Host user's Azure CLI state | `az login` on the host |
| Native MCP with recommended `host_shared` policy | Host user's Azure CLI state | `az login` on the host |
| Docker MCP, default | Volume `kusto-query-cli-mcp-azure-state` at `/root/.azure` | MCP `LOGIN`, complete device flow, then verify `AUTH_STATUS` |
| Docker MCP, host-shared | Host `~/.azure` mounted at `/root/.azure` | `az login` on the host; launch with `--share-host-azure-state` |
| Docker CLI | Compose volume `kusto-query-cli-azure-state` | `./docker/cli.sh az login` |

Compose may prefix its volume name with the project name. CLI and MCP defaults
are intentionally separate; logging into one does not automatically log into the
other. Existing volume names are preserved across application upgrades.

## MCP authentication

For native MCP, set `MCP_AZURE_AUTH_MODE=host_shared` to keep login/logout managed
by host commands, as in the [native client example](mcp.md#native-python). Without
that setting, the default `container_managed` policy allows the native process to
manage login/logout in its own Azure state directory, despite running outside a
container. Policy and credential location are separate choices.

Call `AUTH_STATUS` before querying. In container-managed mode, `LOGIN` can initiate
a device-code flow. Complete the browser instructions and check `AUTH_STATUS`
again. Starting a login process does not mean it succeeded.

In host-shared mode, `LOGIN` and `LOGOUT` direct you to manage authentication on the
host. They do not log in or out inside the container. Install Azure CLI on the
host and use `az login`, `az account set --subscription '<subscription-id>'`, or
`az logout` there as needed. This mode can help when organizational policy
requires a host interactive login instead of device-code authentication.

To isolate Docker MCP sessions, set a distinct `AZURE_STATE_VOLUME` in each
client's environment. Otherwise, successive containers and concurrent sessions
using the same volume share credentials, subscription cache, and proxy settings.

## State changes

`LOGOUT`, `az logout`, and removal of Azure-state volumes affect future sessions.
Use them when intentionally signing out or resetting state, not as the first
troubleshooting step. Do not commit credentials or include tokens and device
codes in shared logs. The project's named-volume mount uses `/root/.azure`; keep
that in mind if customizing Azure CLI configuration directories.
