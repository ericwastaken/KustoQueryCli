from lib.k2run import k2run

# Call up the runner
df = k2run()

# Output the results as JSON
print(df.to_json(orient='records', indent=2, date_format='iso'))
