import pandas as pd
import sys

xls = pd.ExcelFile('Energy_MA_Report_Async_20260330_120838_copy.xlsx')
print('=== SHEET NAMES ===')
print(xls.sheet_names)

for s in ['Upstream', 'Midstream', 'OFS', 'R&M', 'P&U', 'JV & Partnerships', 'Review Queue', 'Rejected by AI']:
    if s not in xls.sheet_names:
        continue
    df = pd.read_excel(xls, sheet_name=s)
    print(f'\n===== [{s}] : {len(df)} rows =====')
    for _, row in df.iterrows():
        headline = str(row.get('Headline',''))
        buyer = str(row.get('Buyer',''))
        seller = str(row.get('Seller',''))
        rej = str(row.get('Rejection Reason',''))
        conf = row.get('CONFIDENCE THRESHOLDS', row.get('Confidence',''))
        print(f'  H: {headline[:120]}')
        if s == 'Rejected by AI':
            print(f'     REASON: {rej[:100]}')
        else:
            print(f'     Buyer={buyer[:40]} | Seller={seller[:40]} | Conf={conf}')
