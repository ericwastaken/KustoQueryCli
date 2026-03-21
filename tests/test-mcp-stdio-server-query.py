#!/usr/bin/env python3
"""
MCP stdio QUERY script

Starts the local MCP stdio server (or Docker wrapper) and performs:
  1) initialize
  2) optional LOGIN (if --login-subscription-id is provided)
  3) tools/call QUERY with provided parameters

Prints the server responses as pretty JSON, then exits.

Usage examples:
  python tests/test-mcp-stdio-server-query.py \
    --cluster-url https://CLUSTER.kusto.windows.net \
    --database MyDb \
    --query "MyTable | take 5"

  python tests/test-mcp-stdio-server-query.py \
    --cluster-url https://CLUSTER.kusto.windows.net \
    --database MyDb \
    --query "MyTable | take 5" \
    --login-subscription-id <SUB_ID> --docker
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional
import select


# Project root (one level up from this file's directory: ./tests)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)


def write_frame(proc: subprocess.Popen, obj: dict) -> None:
    """Write a single ND-JSON line to the server stdin."""
    line = json.dumps(obj, separators=(",", ":")) + "\n"
    proc.stdin.write(line.encode("utf-8"))  # type: ignore[arg-type]
    proc.stdin.flush()  # type: ignore[union-attr]


def read_frame(proc: subprocess.Popen) -> Optional[dict]:
    """Read a single ND-JSON line from server stdout and parse as JSON; None on EOF."""
    line = proc.stdout.readline()  # type: ignore[assignment]
    if not line:
        return None
    while line in (b"\r\n", b"\n"):
        line = proc.stdout.readline()  # type: ignore[assignment]
        if not line:
            return None
    try:
        return json.loads(line.decode("utf-8"))
    except Exception:
        return {"_raw": line.decode("utf-8", "replace")}


def pretty(title: str, payload: Optional[dict]) -> None:
    print(f"\n=== {title} ===")
    if payload is None:
        print("<no response>")
    else:
        print(json.dumps(payload, indent=2))


def build_query_arguments(
    cluster_url: str,
    database: str,
    kql: str,
) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "cluster_url": cluster_url,
        "database": database,
        "query": kql,
    }
    return args


def run(
    *,
    use_docker: bool,
    login_subscription_id: Optional[str],
    query_args: Dict[str, Any],
) -> int:
    # Select command to start the MCP stdio server
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
        # initialize
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kusto-query-cli-query", "version": "1.0"},
                },
            },
        )
        pretty("initialize", read_frame(proc))

        next_id = 2

        # Optional LOGIN
        if login_subscription_id:
            write_frame(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "tools/call",
                    "params": {
                        "name": "LOGIN",
                        "arguments": {"subscription_id": login_subscription_id},
                    },
                },
            )
            pretty("tools/call LOGIN", read_frame(proc))
            next_id += 1

        # Perform QUERY
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "tools/call",
                "params": {"name": "QUERY", "arguments": query_args},
            },
        )
        query_resp = read_frame(proc)
        pretty("tools/call QUERY", query_resp)

        # Drain any stderr output for visibility without blocking indefinitely
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

        # Exit code: 0 on success JSON-RPC result, 1 otherwise
        if isinstance(query_resp, dict) and ("result" in query_resp or "_raw" in query_resp):
            return 0
        return 1
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
    parser = argparse.ArgumentParser(description="MCP stdio QUERY helper")
    parser.add_argument(
        "--cluster-url",
        required=True,
        help="QUERY: cluster URL (e.g. https://<cluster>.kusto.windows.net)",
    )
    parser.add_argument("--database", required=True, help="QUERY: database name")
    parser.add_argument("--query", dest="kql", required=True, help="QUERY: KQL string")
    parser.add_argument(
        "--login-subscription-id",
        help="Optional: call LOGIN first with this subscription id",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Start server via ./docker-mcp.sh instead of local Python",
    )

    args = parser.parse_args()

    qargs = build_query_arguments(
        cluster_url=args.cluster_url,
        database=args.database,
        kql=args.kql,
    )

    os.chdir(ROOT)
    return run(
        use_docker=bool(args.docker),
        login_subscription_id=args.login_subscription_id,
        query_args=qargs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
