import pandas as pd
df = pd.read_excel('energy_scraper/Energy_MA_Report_TEMP_AUDIT.xlsx', sheet_name='Website Processing Log')
failed_df = df[df['Status'] != 'SUCCESS']
print("FAILED SITES:")
for _, row in failed_df.iterrows():
    print(f"- {row['Website']}: {row['Status']} | {row['Error Info']}")

empty_df = df[(df['Status'] == 'SUCCESS') & (df['Articles Found'] == 0)]
print("\nZERO ARTICLES FOUND:")
for _, row in empty_df.iterrows():
    print(f"- {row['Website']}")
