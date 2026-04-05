import pandas as pd
df = pd.read_excel('energy_scraper/Energy_MA_Report_TEMP_AUDIT.xlsx', sheet_name='Website Processing Log')

with open('failures.txt', 'w', encoding='utf-8') as f:
    f.write(f"{'Website':40s} | {'Status':15s} | {'Art':>4s} | Issues\n")
    f.write("-" * 120 + "\n")
    for _, row in df.iterrows():
        status = str(row['Status'])
        issues = str(row['Issues Encountered'])
        articles = row['Articles in Date Range']
        if '❌' in status or '⚠️' in status or issues != 'nan' or pd.isna(articles) or articles == 0:
            f.write(f"{str(row['Website']):40s} | {status:15s} | {str(articles):>4s} | {issues}\n")
