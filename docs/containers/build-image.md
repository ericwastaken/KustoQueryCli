# Build a container image

Use a local build when developing, customizing, or running code from a checkout.
Docker and Buildx must be available, and Docker must be running.

```bash
unset KQC_IMAGE
./docker-mcp-build.sh
```

Despite its historical name, the helper builds the common application image for
MCP, CLI, and wrapper use. It prints only the resulting image tag on stdout;
progress and diagnostics go to stderr. It uses an existing local image if present.

The tag version comes from `KUSTO_QUERY_CLI_VERSION`, then the canonical
`mcp-wrapper-version` file, with `dev` as the helper's fallback. The override changes
the image tag; it does not change application metadata or prepare a release.

To rebuild after editing source:

```bash
./docker-mcp-build.sh --force
```

`./docker-mcp.sh --force` rebuilds before starting MCP. The CLI also accepts a
leading `--force`, for example `./docker-run.sh --force python k2json.py --help`.
The build helper and these flags reject a set `KQC_IMAGE`; unset it first.
Windows CMD equivalents use `.bat`, and `set KQC_IMAGE=` clears the selection.

For a custom local tag using the root Dockerfile:

```bash
docker build -t kusto-query-cli:development .
KQC_IMAGE=kusto-query-cli:development ./docker-run.sh python k2json.py --help
```

Direct `docker compose build` is also available for development: Compose includes
`docker-compose.override.yml`, which adds the build configuration. Runtime
launchers select the base Compose file separately after choosing an image.

A local build uses the Docker builder's selected platform. Release checks validate
both supported Linux architectures; a successful local build alone does not mean
all release checks passed. See [Container development](../development/containers.md)
and [Release preparation](../../RELEASING.md).
