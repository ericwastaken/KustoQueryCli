"""
k2csv.py: A script to execute a Kusto query and output the results in CSV format.
This script uses lib.k2run to handle query execution and common CLI arguments.
"""

from lib.k2run import k2run

# Execute the query using the shared runner
df = k2run()

# Output the resulting pandas DataFrame as CSV to stdout
print(df.to_csv(index=False))
