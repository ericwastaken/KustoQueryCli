"""Compatibility launcher; keep this path stable for existing callers."""
from kusto_query_cli.cli.runner import main


if __name__ == "__main__":
    main("csv")
