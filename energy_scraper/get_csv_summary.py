import pandas as pd
import os

xls_file = 'Energy_MA_Report_Async_20260330_111857.xlsx'
if os.path.exists(xls_file):
    xls = pd.ExcelFile(xls_file)
    dfs = []
    for sheet in xls.sheet_names:
        if any(x in sheet for x in ['Upstream', 'Midstream', 'OFS', 'R&M', 'P&U', 'Output', 'JV']):
            df = pd.read_excel(xls_file, sheet_name=sheet)
            df['Origin_Sheet'] = sheet
            dfs.append(df)
    
    if dfs:
        final = pd.concat(dfs, ignore_index=True)
        # Simplify for audit
        columns = ['Headline', 'Buyer', 'Seller', 'Asset', 'Date', 'Value', 'Link', 'Origin_Sheet']
        final_subset = final[[c for c in columns if c in final.columns]]
        final_subset.to_csv('audit_data.csv', index=False)
        print(f"Exported {len(final_subset)} rows to audit_data.csv")
    else:
        print("No relevant sheets found.")
else:
    print(f"File {xls_file} not found.")
