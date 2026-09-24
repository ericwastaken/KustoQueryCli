"""Compatibility launcher; keep this path stable for existing callers."""
import asyncio
from kusto_query_cli.mcp.server import run


if __name__ == "__main__":
    asyncio.run(run())
