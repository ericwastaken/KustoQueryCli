import os
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.helpers import dataframe_from_result_table

"""
lib/KustoHandler.py: Helper functions for executing KQL queries using the Azure Kusto SDK.
Uses Azure CLI authentication to connect to Azure Data Explorer (ADX) clusters.
"""


def execute_adx_query(
    adx_url: str | None = None,
    database_name: str | None = None,
    query: str | None = None,
    *,
    # Newer keyword names used by the MCP wrapper
    cluster_url: str | None = None,
    database: str | None = None,
    # Optional proxy-related args
    socks5_proxy: str | None = None,
    socks5_dns: bool | None = None,
):
    """
    Executes a query against an Azure Data Explorer (ADX) database and returns the results as a DataFrame.

    Accepts both legacy parameter names (adx_url, database_name) and newer names (cluster_url, database)
    for backwards/forwards compatibility with different callers.

    Parameters:
    - adx_url / cluster_url (str): The URL of the ADX cluster.
    - database_name / database (str): The name of the database to query.
    - query (str): The Kusto query to execute.
    - socks5_proxy (str, optional): SOCKS5 proxy in the form "host:port" or a full URL
      like "socks5://host:port" or "socks5h://host:port". When provided, requests from
      the Azure Kusto SDK will be routed through this proxy for the duration of the call.
    - socks5_dns (bool, optional): If True, perform DNS resolution via the proxy (socks5h).
      If False/None, resolve DNS locally (socks5).

    Returns:
    - DataFrame: The query results.
    """
    # Resolve effective parameters supporting both naming conventions
    effective_url = cluster_url or adx_url
    effective_db = database or database_name

    if not effective_url:
        raise ValueError("Missing required parameter: adx_url/cluster_url")
    if not effective_db:
        raise ValueError("Missing required parameter: database_name/database")
    if not query:
        raise ValueError("Missing required parameter: query")

    # Prepare optional proxy environment overrides when a SOCKS5 proxy is requested
    proxy_env_keys = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ]
    original_env: dict[str, str | None] = {}

    def _normalize_socks_proxy_url(raw: str, use_proxy_dns: bool | None) -> str:
        # Accept already-schemed URLs; otherwise prepend socks5 or socks5h
        lower = raw.lower()
        if lower.startswith("socks5://") or lower.startswith("socks5h://"):
            return raw
        scheme = "socks5h" if use_proxy_dns else "socks5"
        return f"{scheme}://{raw}"

    try:
        if socks5_proxy:
            proxy_url = _normalize_socks_proxy_url(socks5_proxy.strip(), socks5_dns)
            # Capture originals and set overrides
            for k in proxy_env_keys:
                original_env[k] = os.environ.get(k)
                os.environ[k] = proxy_url

        # For simplicity in this code, we're using Azure CLI authentication.
        kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(effective_url)

        # Create a Kusto client
        client = KustoClient(kcsb)

        # Execute the query
        response = client.execute(effective_db, query)

        # Convert the response to a Pandas DataFrame
        df = dataframe_from_result_table(response.primary_results[0])

        return df
    finally:
        # Restore environment to its original state
        if original_env:
            for k, v in original_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
