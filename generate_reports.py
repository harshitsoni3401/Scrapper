from fpdf import FPDF
import os

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", "B", 16)
pdf.cell(40, 10, "How It Works")
pdf.ln(10)
pdf.set_font("Helvetica", "", 12)
pdf.multi_cell(0, 10, "This is the Energy MA Scraper How It Works report.")
pdf.multi_cell(0, 10, "- Adaptive Fetching")
pdf.multi_cell(0, 10, "- ARIA Brain")
pdf.multi_cell(0, 10, "- Agentic QA")

if not os.path.exists('docs'):
    os.makedirs('docs')

pdf.output("docs/How_It_Works.pdf")

pdf2 = FPDF()
pdf2.add_page()
pdf2.set_font("Helvetica", "B", 16)
pdf2.cell(40, 10, "AI Brain Upgrade Plan")
pdf2.ln(10)
pdf2.set_font("Helvetica", "", 12)
pdf2.multi_cell(0, 10, "This is the AI Brain Upgrade Plan.")
pdf2.multi_cell(0, 10, "- RunContextManager")
pdf2.multi_cell(0, 10, "- Enriched Extraction")
pdf2.multi_cell(0, 10, "- Strategic Rationale")

pdf2.output("docs/AI_Brain_Upgrade_Plan.pdf")
print("Done")
