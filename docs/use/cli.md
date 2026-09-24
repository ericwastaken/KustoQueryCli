# Use the CLI

Use `k2json.py` for JSON records or `k2csv.py` for CSV. Both accept a query string,
a query file, or stdin and require a database and ADX cluster URL.

## Native Python

Clone the repository, install Python 3.12+ and Azure CLI, and create an environment:

```bash
git clone https://github.com/ericwastaken/KustoQueryCli.git
cd KustoQueryCli
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
az login
```

On Windows CMD, activate with `venv\Scripts\activate.bat`. On Apple Silicon,
prefer a native ARM Python interpreter. Dependencies
are shared with MCP; install Azure CLI separately for native use.

Use the account authorized for your cluster. Replace the placeholders below:

```bash
python k2json.py --query '<table> | take 10' --database '<database>' --adxUrl 'https://<cluster>'
python k2csv.py --queryFile ./queries/example.kql --database '<database>' --adxUrl 'https://<cluster>' > output.csv
printf '%s\n' '<table> | count' | python k2json.py --database '<database>' --adxUrl 'https://<cluster>'
```

Create the query file before using the file example. Supply one query source;
if several are supplied, query text takes precedence over file and stdin.

## Docker

Start Docker and run from the repository root:

```bash
./docker-run.sh az login
./docker-run.sh python k2json.py --query '<table> | take 10' --database '<database>' --adxUrl 'https://<cluster>'
./docker-run.sh python k2csv.py --queryFile ./queries/example.kql --database '<database>' --adxUrl 'https://<cluster>' > output.csv
```

The launcher builds the local image if needed. For another image, see
[Use a container image](../containers/use-image.md). On Windows CMD, use
`docker-run.bat` and double quotes around argument values. File paths passed to
Python inside the Linux container use Linux separators.

Compose mounts the checkout's `queries/` directory at `/usr/src/app/queries`.
Put query files there when using that mount. Query strings do not require a file.
Authentication is persisted in the CLI's Azure state volume, separate from the
MCP launcher's default volume. See [Authentication](authentication.md).

See the [CLI reference](../reference/cli.md) for flags and
[Proxy configuration](proxy.md) for SOCKS options.
