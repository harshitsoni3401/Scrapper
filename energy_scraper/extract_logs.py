import pandas as pd

def extract_all_sheets(filename):
    try:
        xls = pd.ExcelFile(filename)
        sheet_map = {
            "Log": "Website Processing Log",
            "Issues": "Issue and Solution",
            "Dashboard": "Summary Dashboard",
            "Rejected": "Rejected by AI",
            "Review": "Review Queue"
        }
        
        for key, sheet_name in sheet_map.items():
            if sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                print(f"\n--- {sheet_name} ---")
                if key == "Log":
                    cols = ['Website', 'Status', 'Issues / Errors encountered', 'Resolution Applied']
                    existing_cols = [c for c in cols if c in df.columns]
                    print(df[existing_cols].head(100).to_string())
                elif key == "Rejected":
                    print(df[['Headline', 'Rejection Reason']].to_string())
                elif key == "Dashboard":
                    print(df.to_string())
                else:
                    print(df.to_string())
            else:
                print(f"Sheet '{sheet_name}' not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_all_sheets('Energy_MA_Report_Async_20260330_111857.xlsx')
