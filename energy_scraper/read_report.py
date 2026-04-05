import pandas as pd
import sys

f = 'Energy_MA_Report_Async_20260330_093721.xlsx'
xlsx = pd.ExcelFile(f, engine='openpyxl')
print('SHEETS:', xlsx.sheet_names)

for sh in xlsx.sheet_names:
    df = pd.read_excel(xlsx, sheet_name=sh)
    if 'Headline' not in df.columns:
        continue
    print(f'\n=== SHEET: {sh} ({len(df)} rows) ===')
    cols = [c for c in ['Headline','Industry','Sector','Source','Value','Deal Type','CONFIDENCE THRESHOLDS'] if c in df.columns]
    for _, row in df.iterrows():
        parts = []
        for c in cols:
            parts.append(f'{c[:8]}={str(row.get(c,""))[:50]}')
        print('  | '.join(parts))

xlsx.close()
