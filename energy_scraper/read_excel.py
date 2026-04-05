import pandas as pd
import sys

def read_excel_data(filename):
    try:
        xls = pd.ExcelFile(filename)
        all_data = []
        for sheet_name in xls.sheet_names:
            if any(s in sheet_name for s in ['Upstream', 'Midstream', 'OFS', 'R&M', 'P&U', 'Output', 'JV']):
                df = pd.read_excel(xls, sheet_name=sheet_name)
                # Keep only what we need for cross-checking
                cols = ['Headline', 'Date', 'Link']
                # Filter to only existing columns
                existing_cols = [c for c in cols if c in df.columns]
                subset = df[existing_cols].copy()
                subset['Sheet'] = sheet_name
                all_data.append(subset)
        
        final_df = pd.concat(all_data, ignore_index=True)
        # Filter dates to March 28-30, 2026
        # Assuming Date is in a parsable format or already datetime
        final_df['Date_Parsed'] = pd.to_datetime(final_df['Date'], errors='coerce')
        mask = (final_df['Date_Parsed'] >= '2026-03-28') & (final_df['Date_Parsed'] <= '2026-03-31')
        period_df = final_df[mask].copy()
        print(period_df[['Headline', 'Date', 'Sheet', 'Link']].to_string())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    read_excel_data('Energy_MA_Report_Async_20260330_111857.xlsx')
