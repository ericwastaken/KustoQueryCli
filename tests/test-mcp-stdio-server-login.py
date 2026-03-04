#!/usr/bin/env python3
"""
Minimal MCP stdio login script

Starts the local MCP stdio server (or Docker wrapper) and performs:
  1) initialize
  2) tools/call LOGIN with a provided subscription_id

Prints the server responses as pretty JSON, then exits.

Usage examples:
  python test/test-mcp-stdio-server-login.py --subscription-id <SUB_ID>
  python test/test-mcp-stdio-server-login.py --subscription-id <SUB_ID> --docker
"""

import argparse
import json
import os
import subprocess
import sys
import time
import select


# Project root (one level up from this file's directory: ./test)
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TEST_DIR)


def write_frame(proc: subprocess.Popen, obj: dict) -> None:
    """Write a single ND-JSON line to the server stdin."""
    line = json.dumps(obj, separators=(",", ":")) + "\n"
    proc.stdin.write(line.encode("utf-8"))  # type: ignore[arg-type]
    proc.stdin.flush()  # type: ignore[union-attr]


def read_frame(proc: subprocess.Popen) -> dict | None:
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


def pretty(title: str, payload: dict | None) -> None:
    print(f"\n=== {title} ===")
    if payload is None:
        print("<no response>")
    else:
        print(json.dumps(payload, indent=2))


def run(subscription_id: str, use_docker: bool) -> int:
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
        # 1) initialize
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kusto-query-cli-login", "version": "1.0"},
                },
            },
        )
        pretty("initialize", read_frame(proc))

        # 2) tools/call LOGIN
        write_frame(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "LOGIN",
                    "arguments": {"subscription_id": subscription_id},
                },
            },
        )
        login_resp = read_frame(proc)
        pretty("tools/call LOGIN", login_resp)

        # Drain any stderr output for visibility without blocking indefinitely
        try:
            if proc.stderr is not None:
                # Give the server a brief moment to flush diagnostics
                time.sleep(0.1)
                drained = []
                # Non-blocking drain using select; read small chunks while available
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
        if isinstance(login_resp, dict) and ("result" in login_resp or "_raw" in login_resp):
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
    parser = argparse.ArgumentParser(description="MCP stdio LOGIN helper")
    parser.add_argument(
        "--subscription-id",
        required=True,
        help="Azure subscription ID to pass to LOGIN",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Start server via ./docker-mcp.sh instead of local Python",
    )
    args = parser.parse_args()

    return run(args.subscription_id, args.docker)


if __name__ == "__main__":
    raise SystemExit(main())
