"""Compatibility launcher; keep this path stable for existing callers."""
from kusto_query_cli.mcp.wrapper import main


if __name__ == "__main__":
    main()
