from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.helpers import dataframe_from_result_table


def execute_adx_query(adx_url, database_name, query):
    """
    Executes a query against an Azure Data Explorer (ADX) database and returns the results as a DataFrame.

    Parameters:
    - adx_url (str): The URL of the ADX cluster.
    - database_name (str): The name of the database to query.
    - query (str): The Kusto query to execute.

    Returns:
    - DataFrame: The query results.
    """
    # For simplicity in this code, we're using Azure CLI authentication.
    kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(adx_url)

    # Create a Kusto client
    client = KustoClient(kcsb)

    # Execute the query
    response = client.execute(database_name, query)

    # Convert the response to a Pandas DataFrame
    df = dataframe_from_result_table(response.primary_results[0])

    return df
