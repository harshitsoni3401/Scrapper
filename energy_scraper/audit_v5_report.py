import pandas as pd
import json
import os
import shutil

original_file = r"C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run\energy_scraper\Energy_MA_Report_Async_20260330_012207.xlsx"
temp_file = r"C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run\energy_scraper\temp_audit_v5_final.xlsx"

if not os.path.exists(original_file):
    print(f"ERROR: File not found at {original_file}")
    exit(1)

try:
    shutil.copy2(original_file, temp_file)
    with pd.ExcelFile(temp_file, engine='openpyxl') as xlsx:
        all_sheets_data = {}
        for sheet_name in xlsx.sheet_names:
            if sheet_name in ["Summary", "Rejected by AI", "User Feedback for AI Learning"]:
                continue
            df = pd.read_excel(xlsx, sheet_name=sheet_name)
            if not df.empty:
                all_sheets_data[sheet_name] = df.to_dict(orient="records")

    print("---START_JSON---")
    print(json.dumps(all_sheets_data, indent=2))
    print("---END_JSON---")

except Exception as e:
    print(f"ERROR: {e}")
# We leave the temp_file there to avoid PermissionError during remove
