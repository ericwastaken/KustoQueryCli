# SOCKS proxy configuration

Use a SOCKS5 proxy when your network requires one to reach Azure or ADX. The host
and port must be reachable from the process making the request. Inside Docker,
`localhost` refers to the container, not the host machine.

## CLI

Add `--use-socks5 host:port` and, when DNS should go through the proxy,
`--use-socks5-dns`:

```bash
python k2json.py --query '<table> | take 10' --database '<database>' --adxUrl 'https://<cluster>' --use-socks5 proxy.example:1080 --use-socks5-dns
```

These flags configure the CLI process. They do not write the MCP proxy-state file.

## MCP and one-shot wrapper

Call `PROXY_CONFIG` with direct MCP arguments:

```json
{
    "socks5_proxy": "proxy.example:1080",
    "socks5_dns": true
}
```

Pass `{}` to inspect the current configuration. To intentionally remove the
persisted configuration, pass `{"clear":true}`. The wrapper uses the same fields
inside an `action`/`params` envelope.

Configuration persists in `~/.azure/mcp_proxy_config.json` within the selected
Azure state directory. It survives tool calls and, with a persistent Docker mount,
container restarts. It is shared by sessions using the same state directory.

If authentication returns browser or device-login instructions, that browser must
also reach the relevant Microsoft login endpoints. Configuring the tool's proxy
does not configure the browser. See [Authentication](authentication.md).
