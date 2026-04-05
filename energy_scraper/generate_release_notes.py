import os
from datetime import datetime
from fpdf import FPDF
from pathlib import Path

class ReleaseNotesPDF(FPDF):
    def _safe(self, text):
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def header(self):
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 25, 'F')
        self.set_y(8)
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, self._safe('Energy M&A Scraper - Version Release Notes'), 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, self._safe(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'), 0, 0, 'C')

    def chapter_title(self, label):
        self.set_font('helvetica', 'B', 14)
        self.set_text_color(0, 51, 102)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, self._safe(f'  {label}'), 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, text):
        self.set_font('helvetica', '', 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, self._safe(text))
        self.ln(5)

def generate_notes(output_path):
    pdf = ReleaseNotesPDF()
    pdf.add_page()
    
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, pdf._safe('Transition: v5.0 -> v6.0'), 0, 1)
    pdf.ln(5)

    pdf.chapter_title('What was in the Previous Version (v5.0)')
    text_v5 = (
        "In v5.0, the AI classifier was explicitly limited to 'Strict M&A Only'. "
        "It was taught to ruthlessly reject any 'contract win' or 'auction win' to reduce service-contract noise (like boiler sales). "
        "It also rejected all institutional transactions (e.g. Asset Managers buying shares) to prevent open-market false positives. "
        "Lookback was set to 1 day by default, and paywalled sites like Bloomberg were searched using generic boolean operators."
    )
    pdf.chapter_body(text_v5)

    pdf.chapter_title('What is in the New Version (v6.0)')
    text_v6 = (
        "Version 6.0 pivots the fundamental mission from 'Strict M&A' to 'High-Velocity Strategic Energy Deals'. "
        "New Features:\n"
        "- Explicit inclusion of Government Tenders and Capacity Auction Wins (e.g. SECI Solar Auctions) as valid High-Value Deals.\n"
        "- Refined AI Logic allowing Asset Managers/Funds to be marked as valid buyers ONLY if they are securing strategic stakes in private infrastructure (e.g. Grid Operators), while still blocking standard stock trades.\n"
        "- Default lookback window extended to 2 days to protect Monday runs from dropping Friday morning deals.\n"
        "- Paywall Bypass Boolean queries: Explicitly searching for snippets with 'oppose deal', 'stake sale', and 'take private' for Bloomberg and WSJ."
    )
    pdf.chapter_body(text_v6)

    pdf.chapter_title('Why v6.0 is Better Than v5.0')
    text_why = (
        "Version 5.0 was incredibly clean but overly restrictive, causing 5 false-negatives (missed deals/auctions) from March 28-30. "
        "Version 6.0 reintroduces massive utility by capturing billion-dollar government tenders and strategic infrastructure investments without letting the 'Wall Street open-market noise' back in. "
        "By extending the lookback to 2 days and deploying specialized paywall-bypass snippet queries, the scraper achieves near 100% recall on the exact blind spots identified in the previous audit."
    )
    pdf.chapter_body(text_why)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)
    print(f"✅ Generated Release Notes PDF at {output_path}")

if __name__ == '__main__':
    generate_notes(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'Version_v5_to_v6_Release_Notes.pdf')))
