from lib.k2run import k2run

# Call up the runner
df = k2run()

# Output the results as CSV
print(df.to_csv(index=False))
