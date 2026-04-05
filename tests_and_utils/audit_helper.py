import pandas as pd
import sys

def audit_report(file_path):
    xl = pd.ExcelFile(file_path)
    lines = []
    lines.append("--- Accepted Deals ---")
    total_deals = 0
    for sheet in ['Upstream', 'Midstream', 'OFS', 'R&M', 'P&U']:
        if sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet)
            if not df.empty:
                lines.append(f"\n[{sheet}] ({len(df)} deals):")
                for _, row in df.iterrows():
                    headline = str(row.get('Headline', 'N/A'))
                    site = str(row.get('Website', 'N/A'))
                    buyer = str(row.get('Buyer', 'N/A'))
                    seller = str(row.get('Seller', 'N/A'))
                    lines.append(f" - {headline[:100]} | {site} | B:{buyer} | S:{seller}")
                total_deals += len(df)
            
    if 'Rejected by AI' in xl.sheet_names:
        df_rej = pd.read_excel(xl, sheet_name='Rejected by AI')
        lines.append(f"\n--- Rejected Deals ({len(df_rej)}) ---")
        for _, row in df_rej.head(10).iterrows():
            headline = str(row.get('Headline', 'N/A'))
            reason = str(row.get('AI Reason', 'N/A'))
            lines.append(f" - {headline[:60]}... | Reason: {reason}")

    if 'Website Processing Log' in xl.sheet_names:
        df_log = pd.read_excel(xl, sheet_name='Website Processing Log')
        lines.append(f"\n--- Website Issues ---")
        issues = df_log[df_log['Access Mode'].isin(['Failed', 'Blocked'])]
        for _, row in issues.iterrows():
            site = str(row.get('Site', 'N/A'))
            mode = str(row.get('Access Mode', 'N/A'))
            rends = str(row.get('Render Type', 'N/A'))
            lines.append(f" Failed: {site} | Mode: {mode} | Render: {rends}")

    with open('tests_and_utils/audit_report_out.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

if __name__ == '__main__':
    audit_report(sys.argv[1])
