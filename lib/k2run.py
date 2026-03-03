import argparse
import os
import sys
import re
from lib.KustoHandler import execute_adx_query
from lib.AzureCliHelper import check_azure_cli_logged_in

"""
lib/k2run.py: Common runner logic for Kusto CLI scripts.
Handles argument parsing, input source selection (file, string, or stdin), 
proxy configuration, and authentication checks.
"""


def validate_socks5_proxy(proxy_str):
    """
    Validates the <host>:<port> format and port range for a SOCKS5 proxy.
    Used by argparse.
    """
    pattern = r'^([^:]+):(\d+)$'
    match = re.match(pattern, proxy_str)
    if not match:
        raise argparse.ArgumentTypeError("Proxy must be in format <host>:<port>")
    
    host, port_str = match.groups()
    try:
        port = int(port_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Port '{port_str}' must be an integer")
        
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError(f"Port '{port}' must be in range 1-65535")
        
    return proxy_str


def k2run():
    """
    Parses command-line arguments and executes the Kusto query.
    Returns a pandas DataFrame containing the results.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Query Azure Data Explorer from a query file and output results.')
    parser.add_argument('--queryFile', type=str, required=False, help='Full path to the query text file.')
    parser.add_argument('--query', type=str, required=False, help='The query string itself.')
    parser.add_argument('--database', type=str, required=True, help='The name of the database to query against.')
    parser.add_argument('--adxUrl', type=str, required=True, help='The Azure Data Explorer cluster URL.')
    parser.add_argument('--use-socks5', type=validate_socks5_proxy, help='Use a SOCKS5 proxy in <host>:<port> format.')
    parser.add_argument('--use-socks5-dns', action='store_true', help='Use the proxy for DNS resolution (socks5h://).')
    args = parser.parse_args()

    # Determine query source
    query = None
    if args.query:
        query = args.query
    elif args.queryFile:
        # Read the query from the file
        try:
            with open(args.queryFile, 'r') as file:
                query = file.read()
        except FileNotFoundError:
            print(f"Error: Query file not found at {args.queryFile}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading query file: {e}")
            sys.exit(1)
    elif not sys.stdin.isatty():
        # Read from stdin if it's not a terminal (piped input)
        try:
            query = sys.stdin.read().strip()
        except Exception as e:
            print(f"Error reading query from stdin: {e}")
            sys.exit(1)

    # Check if a query was provided
    if not query:
        print("Error: No query provided. Use --queryFile, --query, or pipe a query to stdin.")
        parser.print_help()
        sys.exit(1)

    # Set proxy if requested
    if args.use_socks5:
        protocol = "socks5h" if args.use_socks5_dns else "socks5"
        proxy_url = f"{protocol}://{args.use_socks5}"
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url

    # Check that the user is logged in to Azure CLI (this will raise an exception if not)
    check_azure_cli_logged_in()

    # Execute the query through the ADX library
    try:
        return execute_adx_query(args.adxUrl, args.database, query)
    except Exception as e:
        # Check for network-related errors in the exception message or type
        error_msg = str(e)
        if "KustoNetworkError" in type(e).__name__ or "ConnectionError" in error_msg or "Max retries exceeded" in error_msg:
            print("\nError: A network issue occurred while connecting to Azure Data Explorer.")
            if args.use_socks5:
                print(f"Check if your SOCKS5 proxy at {args.use_socks5} is reachable and working.")
                if not args.use_socks5_dns:
                    print("This might require DNS resolution through the proxy. Try adding '--use-socks5-dns'.")
            print(f"Details: {error_msg}\n")
            sys.exit(1)
        else:
            # Re-raise or print other errors
            print(f"\nAn error occurred: {e}")
            sys.exit(1)