# CLI reference

`python k2json.py` writes a JSON array of records. `python k2csv.py` writes CSV.
Both use the same arguments and Azure CLI authentication.

| Argument | Meaning |
| --- | --- |
| `--database NAME` | Required ADX database |
| `--adxUrl URL` | Required ADX cluster URL |
| `--query TEXT` | Query supplied directly |
| `--queryFile PATH` | Read query text from a file |
| stdin | Read piped query text when neither query option is supplied |
| `--use-socks5 HOST:PORT` | SOCKS5 proxy |
| `--use-socks5-dns` | Resolve DNS through the SOCKS proxy |
| `--help` | Show argument help |

Precedence is `--query`, then `--queryFile`, then piped stdin. Prefer a single
source to make intent clear. Query-file paths are resolved in the executing
process's filesystem; container paths are not arbitrary host paths.

See [Use the CLI](../use/cli.md) for native/Docker commands,
[Authentication](../use/authentication.md), and [Proxy configuration](../use/proxy.md).
