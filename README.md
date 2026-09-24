# Kusto Query CLI

Query Azure Data Explorer (ADX) from an MCP client or a command line. The CLI
produces JSON or CSV; the MCP server exposes query, authentication, proxy, and
contract-discovery tools. Both use Azure CLI authentication.

## Choose your task

| I want to... | Start here |
| --- | --- |
| Connect an AI client using MCP, natively or in Docker | [Use MCP](docs/use/mcp.md) |
| Run queries and export JSON/CSV, natively or in Docker | [Use the CLI](docs/use/cli.md) |
| Run an existing container image | [Use a container image](docs/containers/use-image.md) |
| Build my own container image | [Build a container image](docs/containers/build-image.md) |
| Use the one-shot JSON action interface | [Use the wrapper](docs/use/wrapper.md) |
| Change Python behavior | [Development setup](docs/development/setup.md), [Python development](docs/development/python.md) |
| Change Docker builds or launchers | [Container development](docs/development/containers.md) |
| Prepare a release | [Release workflow](RELEASING.md) |
| Work on or consume this project as an agent | [Agent instructions](AGENTS.md) |

Native use requires Python 3.12+ and Azure CLI. Docker includes both. You need an
Azure identity authorized for your cluster and the cluster URL/database to query.

Docker launchers build locally by default. They can also select an existing image
explicitly with `KQC_IMAGE=ghcr.io/ericwastaken/kustoquerycli:2.0.0`. Releases publish
Linux AMD64 and ARM64 images to GHCR. See the [image guide](docs/containers/use-image.md).

## Shared guidance

- [Authentication and Azure state](docs/use/authentication.md)
- [SOCKS proxy configuration](docs/use/proxy.md)
- [Troubleshooting](docs/use/troubleshooting.md)
- [CLI reference](docs/reference/cli.md)
- [MCP tools and contract](docs/reference/mcp.md)
- [Configuration reference](docs/reference/configuration.md)
- [Architecture](docs/development/architecture.md) and [testing](docs/development/testing.md)

Application changes are recorded in [CHANGELOG.md](CHANGELOG.md). Canonical action
contracts and payloads remain in [schemas/](schemas/), [examples/](examples/), and
[mcp-contract.md](mcp-contract.md).
