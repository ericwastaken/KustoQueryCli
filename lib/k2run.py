import argparse
from lib.KustoHandler import execute_adx_query
from lib.AzureCliHelper import check_azure_cli_logged_in


def k2run():

    # Check that the user is logged in to Azure CLI (this will raise an exception if not)
    check_azure_cli_logged_in()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Query Azure Data Explorer from a query file and output results.')
    parser.add_argument('--queryFile', type=str, required=True, help='Full path to the query text file.')
    parser.add_argument('--database', type=str, required=True, help='The name of the database to query against.')
    parser.add_argument('--adxUrl', type=str, required=True, help='The Azure Data Explorer cluster URL.')
    args = parser.parse_args()

    # Read the query from the file
    with open(args.queryFile, 'r') as file:
        query = file.read()

    # Execute the query through the ADX library
    return execute_adx_query(args.adxUrl, args.database, query)