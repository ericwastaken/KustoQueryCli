# Use a container image

The same application image runs the CLI, MCP server, and one-shot wrapper. Choose
how to acquire it independently of which interface you use.

| Selection | Behavior |
| --- | --- |
| `KQC_IMAGE` unset | Use the checkout's versioned local image; build it if missing |
| `KQC_IMAGE` set to a tag or digest | Use that exact image if cached, otherwise pull it; never fall back to a local build |

Releases publish `ghcr.io/ericwastaken/kustoquerycli` for Linux AMD64 and ARM64.
Use an exact version such as `2.0.0` or the digest in the matching
[GitHub release](https://github.com/ericwastaken/KustoQueryCli/releases).
Stable releases also update their minor alias (for example `2.0`); `latest` tracks
the highest stable release. Release candidates have only an exact version tag.

## Select an existing image

Set the exact image reference for the launcher. Replace the placeholder with an
existing compatible application image:

```bash
export KQC_IMAGE='ghcr.io/ericwastaken/kustoquerycli:2.0.0'
./docker-run.sh python k2json.py --query '<table> | take 10' --database '<database>' --adxUrl 'https://<cluster>'
```

A digest reference such as `<registry>/<owner>/<image>@sha256:<digest>` selects
immutable image content. A tag uses the cached image when present; run
`docker pull "$KQC_IMAGE"` explicitly to refresh a mutable tag. Registry access or
pull failures stop execution. A locally tagged image can also be selected with
`KQC_IMAGE`; it must already exist locally if it cannot be pulled.

For an MCP client with per-server environment configuration:

```json
{
    "mcpServers": {
        "kusto-query": {
            "command": "/absolute/path/to/KustoQueryCli/docker-mcp.sh",
            "env": {
                "KQC_IMAGE": "ghcr.io/ericwastaken/kustoquerycli:2.0.0"
            }
        }
    }
}
```

On Windows CMD, set the same variable using `set KQC_IMAGE=...` and use the `.bat`
launcher. Client configuration formats can differ; use the client's equivalent
environment setting if it does not support the example format.

Authentication volumes, query-file mounts, and MCP stdio behavior remain the same
for local and selected images. See [Authentication](../use/authentication.md).
The launchers still come from a checkout; remote image selection does not currently
provide a separate launcher installation mechanism.

## Return to local builds

Unset `KQC_IMAGE` before using build helpers or `--force`:

```bash
unset KQC_IMAGE
./docker-mcp-build.sh --force
```

The explicit build helper rejects `KQC_IMAGE`, as do launcher `--force` requests
while an image is selected. This prevents an accidental rebuild when the intention
was to run a published image. See [Build an image](build-image.md).
