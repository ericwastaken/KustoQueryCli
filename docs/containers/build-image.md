# Build a container image

Use a local build when developing, customizing, or running code from a checkout.
Docker and Buildx must be available, and Docker must be running.

```bash
unset KQC_IMAGE
./docker/build.sh
```

The helper builds the common application image for
MCP, CLI, and wrapper use. It prints only the resulting image tag on stdout;
progress and diagnostics go to stderr. It uses an existing local image if present.

The tag version comes from `KUSTO_QUERY_CLI_VERSION`, then the canonical
`kusto_query_cli/assets/mcp-wrapper-version` file, with `dev` as the helper's fallback. The override changes
the image tag; it does not change application metadata or prepare a release.

To rebuild after editing source:

```bash
./docker/build.sh --force
```

`./docker/mcp.sh --force` rebuilds before starting MCP. The CLI also accepts a
leading `--force`, for example `./docker/cli.sh --force python k2json.py --help`.
The build helper and these flags reject a set `KQC_IMAGE`; unset it first.
Windows CMD equivalents use `.bat`, and `set KQC_IMAGE=` clears the selection.

For a custom local tag using the Dockerfile in `docker/`:

```bash
docker build -f docker/Dockerfile -t kusto-query-cli:development .
KQC_IMAGE=kusto-query-cli:development ./docker/cli.sh python k2json.py --help
```

For direct Compose builds, select the development configuration explicitly from
the repository root:

```bash
docker compose --project-directory . --env-file docker/.env \
    -f docker/compose.yaml -f docker/compose.build.yaml build
```

Runtime launchers select only `docker/compose.yaml` after choosing an image. The
explicit project directory preserves query mounts and the existing Compose volume
names regardless of the caller's current directory.

A local build uses the Docker builder's selected platform. Release checks validate
both supported Linux architectures; a successful local build alone does not mean
all release checks passed. See [Container development](../development/containers.md)
and [Release preparation](../development/releases.md).
