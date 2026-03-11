import argparse
import json
import os
import subprocess
import sys
import time
import select


# Simple MCP stdio test script
# - Sends JSON-RPC requests as ND-JSON (newline-delimited JSON)
# - Exercises initialize -> tools/list -> tools/call flows
# - Can target either the local server (python mcp-stdio-server.py) or Docker wrapper (./docker-mcp.sh)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_frame(proc: subprocess.Popen, obj: dict) -> None:
    """
    Write a single ND-JSON line (no Content-Length framing).
    The current Dockerized server expects newline-delimited JSON messages.
    """
    line = json.dumps(obj, separators=(",", ":")) + "\n"
    proc.stdin.write(line.encode("utf-8"))  # type: ignore[arg-type]
    proc.stdin.flush()  # type: ignore[union-attr]


def read_frame(proc: subprocess.Popen) -> dict | None:
    """
    Read a single ND-JSON line from stdout and parse as JSON.
    Returns None on EOF.
    """
    line = proc.stdout.readline()  # type: ignore[assignment]
    if not line:
        return None
    # Skip empty lines
    while line in (b"\r\n", b"\n"):
        line = proc.stdout.readline()  # type: ignore[assignment]
        if not line:
            return None
    try:
        return json.loads(line.decode("utf-8"))
    except Exception:
        return {"_raw": line.decode("utf-8", "replace")}


def pretty(title: str, payload: dict | None) -> None:
    print(f"\n=== {title} ===")
    if payload is None:
        print("<no response>")
    else:
        print(json.dumps(payload, indent=2))

def run_sequence(
    server: str,
    use_docker: bool,
    login_sub: str | None,
    do_logout: bool,
    query_args: dict | None,
) -> int:
    # Select command
    if use_docker:
        cmd = [os.path.join(ROOT, "docker-mcp.sh")]
    else:
        cmd = [sys.executable, os.path.join(ROOT, "mcp-stdio-server.py")]

    print(f"Starting MCP server: {' '.join(cmd)}\n")

    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Always initialize first
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kusto-query-cli-test", "version": "1.0"},
                },
            },
        )
        pretty("initialize", read_frame(proc))

        # List tools
        write_frame(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        list_resp = read_frame(proc)
        pretty("tools/list", list_resp)

        # Optionally LOGIN
        next_id = 3
        if login_sub is not None:
            write_frame(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "tools/call",
                    "params": {"name": "LOGIN", "arguments": {"subscription_id": login_sub}},
                },
            )
            pretty("tools/call LOGIN", read_frame(proc))
            next_id += 1

        # AUTH_STATUS
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "tools/call",
                "params": {"name": "AUTH_STATUS", "arguments": {}},
            },
        )
        pretty("tools/call AUTH_STATUS", read_frame(proc))
        next_id += 1

        # Optional QUERY
        if query_args:
            args = {
                "cluster_url": query_args.get("cluster_url"),
                "database": query_args.get("database"),
                "query": query_args.get("query"),
            }
            write_frame(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "tools/call",
                    "params": {"name": "QUERY", "arguments": args},
                },
            )
            pretty("tools/call QUERY", read_frame(proc))
            next_id += 1

        # Optional LOGOUT
        if do_logout:
            write_frame(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "tools/call",
                    "params": {"name": "LOGOUT", "arguments": {}},
                },
            )
            pretty("tools/call LOGOUT", read_frame(proc))

        # Drain any stderr output (non-fatal diagnostics) without blocking
        try:
            if proc.stderr is not None:
                time.sleep(0.1)
                drained = []
                while True:
                    rlist, _, _ = select.select([proc.stderr], [], [], 0)
                    if not rlist:
                        break
                    chunk = proc.stderr.read(4096)
                    if not chunk:
                        break
                    drained.append(chunk)
                if drained:
                    sys.stderr.write("\n[server stderr]\n" + b"".join(drained).decode("utf-8", "replace") + "\n")
        except Exception:
            pass

        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple MCP stdio test client")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Use ./docker-mcp.sh instead of local python mcp-stdio-server.py",
    )
    parser.add_argument(
        "--login",
        metavar="SUBSCRIPTION_ID",
        help="Call LOGIN with the provided subscription id before other calls",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Call LOGOUT at the end of the sequence",
    )
    parser.add_argument("--cluster", help="QUERY: cluster URL (for tools/call QUERY)")
    parser.add_argument("--database", help="QUERY: database name (for tools/call QUERY)")
    parser.add_argument("--query", dest="kql", help="QUERY: KQL string (for tools/call QUERY)")

    args = parser.parse_args()

    query_args = None
    if args.cluster and args.database and args.kql:
        # Server expects 'cluster_url' and 'query' keys
        query_args = {"cluster_url": args.cluster, "database": args.database, "query": args.kql}

    os.chdir(ROOT)
    return run_sequence(
        server="docker" if args.docker else "local",
        use_docker=args.docker,
        login_sub=args.login,
        do_logout=bool(args.logout),
        query_args=query_args,
    )


if __name__ == "__main__":
    raise SystemExit(main())
