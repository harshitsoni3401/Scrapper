import pandas as pd

try:
    xls = pd.ExcelFile('Energy_MA_Report_Async_20260330_120838_copy.xlsx')
    sheets = ['Upstream', 'Midstream', 'OFS', 'R&M', 'P&U', 'JV & Partnerships', 'Review Queue', 'Rejected by AI']
    
    for s in sheets:
        if s in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=s)
            if not df.empty:
                print(f"\n[{s}] ({len(df)} deals)")
                # Print Headline, Buyer, Seller
                for _, row in df.iterrows():
                    headline = row.get("Headline", "")
                    buyer = row.get("Buyer", "")
                    seller = row.get("Seller", "")
                    print(f"H: {headline}")
                    if s == "Rejected by AI":
                        print(f"  Reject Reason: {row.get('Rejection Reason', '')}")
                    else:
                        print(f"  B: {buyer} | S: {seller}")
except Exception as e:
    print("Error:", e)
