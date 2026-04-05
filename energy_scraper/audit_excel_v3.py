import pandas as pd
import os
import shutil
import json

original_file = r"c:\Users\harsh\OneDrive\Desktop\Scraper Trial Run\energy_scraper\Energy_MA_Report_Async_20260330_003400.xlsx"
temp_file = r"c:\Users\harsh\OneDrive\Desktop\Scraper Trial Run\energy_scraper\temp_audit_v3.xlsx"

try:
    if os.path.exists(temp_file):
        os.remove(temp_file)
    shutil.copy2(original_file, temp_file)
    
    with pd.ExcelFile(temp_file) as xls:
        print(f"Sheets found: {xls.sheet_names}")
        all_data = []
        for sheet_name in xls.sheet_names:
            if sheet_name in ["Summary", "Rejected by AI", "User Feedback for AI Learning"]:
                continue
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if not df.empty:
                relevant_cols = [c for c in ['Headline', 'Buyer', 'Seller', 'Asset', 'Value', 'Source', 'Date', 'Confidence'] if c in df.columns]
                for idx, row in df.iterrows():
                    item = {col: str(row[col]) for col in relevant_cols}
                    item['Sheet'] = sheet_name
                    item['RowIndex'] = idx + 2
                    all_data.append(item)
    
    print("EXTRACTED_DATA_START")
    print(json.dumps(all_data, indent=2))
    print("EXTRACTED_DATA_END")

except Exception as e:
    print(f"Error: {e}")
finally:
    try:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    except:
        pass
