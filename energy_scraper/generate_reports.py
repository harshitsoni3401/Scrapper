"""
generate_reports.py — Generates three professional PDF reports for the Energy M&A Scraper.
Safe version: No non-ASCII characters, no Italic fonts (fpdf2 compatibility).
"""

import os, datetime
from fpdf import FPDF

# Constants
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ACCENT = (20, 80, 140)
LIGHT  = (230, 238, 252)
BLACK  = (30, 30, 30)
WHITE  = (255, 255, 255)
GREEN  = (22, 130, 80)
GREY   = (120, 120, 120)

def new_pdf():
    p = FPDF()
    p.set_auto_page_break(auto=True, margin=20)
    p.set_margins(18, 18, 18)
    return p

def add_header(p: FPDF, title: str):
    p.set_fill_color(*ACCENT)
    p.rect(0, 0, 210, 13, "F")
    p.set_font("helvetica", "B", 8)
    p.set_text_color(*WHITE)
    p.set_xy(3, 2)
    p.cell(0, 9, title[:90])
    p.set_text_color(*BLACK)

def add_footer(p: FPDF):
    p.set_y(-13)
    p.set_font("helvetica", "", 8)
    p.set_text_color(*GREY)
    date_str = datetime.datetime.now().strftime("%d %b %Y")
    p.cell(0, 8, f"Energy MA Scraper  |  {date_str}  |  Page {p.page_no()}", align="C")
    p.set_text_color(*BLACK)

def new_page(p: FPDF, header_title: str):
    p.add_page()
    add_header(p, header_title)
    p.set_y(18)

def cover_page(p: FPDF, title: str, subtitle: str, desc: str):
    p.add_page()
    p.set_fill_color(*ACCENT)
    p.rect(0, 0, 210, 297, "F")
    p.set_font("helvetica", "B", 26)
    p.set_text_color(*WHITE)
    p.set_y(65)
    p.multi_cell(0, 13, title, align="C")
    p.ln(5)
    p.set_font("helvetica", "B", 14) # No italic
    p.multi_cell(0, 8, subtitle, align="C")
    p.ln(8)
    p.set_font("helvetica", "", 10)
    p.set_x(22)
    p.multi_cell(165, 6, desc, align="C")
    p.ln(18)
    p.set_font("helvetica", "", 9)
    date_str = datetime.datetime.now().strftime("%d %B %Y")
    p.cell(0, 7, f"Generated: {date_str}", align="C")

def section(p: FPDF, text: str):
    p.ln(5)
    p.set_fill_color(*ACCENT)
    p.set_text_color(*WHITE)
    p.set_font("helvetica", "B", 11)
    p.cell(0, 8, f"  {text}", fill=True)
    p.ln(10)
    p.set_text_color(*BLACK)

def subsection(p: FPDF, text: str):
    p.ln(3)
    p.set_font("helvetica", "B", 9.5)
    p.set_text_color(*ACCENT)
    p.cell(0, 6, text)
    p.ln(8)
    p.set_text_color(*BLACK)

def body(p: FPDF, text: str):
    p.set_font("helvetica", "", 9)
    p.multi_cell(0, 6, text)
    p.ln(1)

def bullets(p: FPDF, items):
    p.set_font("helvetica", "", 9)
    for item in items:
        p.set_x(p.l_margin + 4)
        p.cell(4, 5.5, "-")
        p.multi_cell(0, 5.5, str(item))
    p.ln(1)

def table(p: FPDF, headers, rows, col_widths=None):
    if col_widths is None:
        w = p.epw / len(headers)
        col_widths = [w] * len(headers)
    p.set_fill_color(*ACCENT)
    p.set_text_color(*WHITE)
    p.set_font("helvetica", "B", 8)
    for i, h in enumerate(headers):
        p.cell(col_widths[i], 7, f" {h}", border=0, fill=True)
    p.ln()
    p.set_font("helvetica", "", 8)
    for ri, row in enumerate(rows):
        if ri % 2 == 0: p.set_fill_color(*LIGHT)
        else: p.set_fill_color(*WHITE)
        p.set_text_color(*BLACK)
        for i, cell_val in enumerate(row):
            p.cell(col_widths[i], 6.5, f" {cell_val[:60]}", border=0, fill=True)
        p.ln()
    p.ln(2)

def callout(p: FPDF, label: str, text: str, color=None):
    if color is None: color = ACCENT
    p.set_fill_color(*color)
    p.set_text_color(*WHITE)
    p.set_font("helvetica", "B", 8.5)
    p.cell(0, 7, f"  {label}", fill=True)
    p.ln(7)
    p.set_fill_color(*LIGHT)
    p.set_text_color(*BLACK)
    p.set_font("helvetica", "", 8.5)
    p.multi_cell(0, 6, f"  {text}", fill=True)
    p.ln(2)

# ---------------------------------------------------------
# REPORT 1: How It Works
# ---------------------------------------------------------
def report_how_it_works():
    title = "Energy MA Scraper: How It Works"
    p = new_pdf()
    cover_page(p, "Energy MA Scraper", "How It Works - Full Technical Architecture", "Walkthrough of the data pipeline, AI filtering, site strategies, and agents.")
    
    new_page(p, title)
    section(p, "1. Executive Summary")
    body(p, "The Energy MA Scraper is an autonomous pipeline monitoring global energy M and A activity. It covers 80+ websites, 10 wire feeds, and 60+ targeted queries. It uses multi-stage AI verification to ensure 100 percent precision.")
    bullets(p, ["80+ targets: Oil, Gas, Renewables, Mining", "6-tier fallback system for fetching", "AI verification eliminates non-energy noise", "Structured Excel output with sector routing"])
    
    section(p, "2. System Architecture")
    table(p, ["File", "Role", "Capability"], [
        ["main.py", "Entry Point", "CLI handles, dependency checks"],
        ["scraper.py", "Orchestrator", "Async parallel site processing"],
        ["fetcher.py", "Engine", "6-tier fallback fetching"],
        ["ai_extractor.py", "AI Brain", "Groq/Gemini verification and extraction"],
        ["config.py", "Brain", "Site definitions and keyword maps"]
    ])
    
    section(p, "3. Data Pipeline")
    subsection(p, "Stage 1: Discovery")
    body(p, "Collects URLs from RSS, JS sites, and Google News in parallel.")
    subsection(p, "Stage 2: AI Gate")
    body(p, "Verifies if the article is a genuine M and A deal using LLMs.")
    subsection(p, "Stage 3: Extraction")
    body(p, "Extracts buyer, seller, value, and rationale.")
    
    p.output(os.path.join(OUTPUT_DIR, "How_It_Works.pdf"))

# ---------------------------------------------------------
# REPORT 2: Enterprise Strategy
# ---------------------------------------------------------
def report_enterprise_strategy():
    title = "Enterprise Strategy Report"
    p = new_pdf()
    cover_page(p, "Enterprise Upgrade", "Security and Cost Optimization Research", "Strategies for office deployment and AI cost management.")
    
    new_page(p, title)
    section(p, "1. Office Laptop Deployment")
    body(p, "To run safely on office hardware, the following mitigations are applied:")
    bullets(p, ["Headless browser mode as default", "Worker count limited to 2-3 to avoid CPU spikes", "Network traffic jitter to avoid detection", "No sensitive data ever leaves the machine (public news only)"])
    
    section(p, "2. Gemini vs Azure OpenAI")
    body(p, "Gemini is recommended for cost-efficiency. Azure is best for deep MS ecosystem integration.")
    table(p, ["Feature", "Google Gemini", "Azure OpenAI"], [
        ["Cost (Pro)", "Lower (~$1.25/1M)", "Higher (~$2.50/1M)"],
        ["Speed (Flash)", "Extremely Fast", "Mini model available"],
        ["Privacy", "Enterprise No-Train", "Enterprise No-Train"]
    ])
    
    section(p, "3. Smart Routing")
    body(p, "Tiered routing: Keyword -> Flash -> Pro. Reducts daily run costs by 70+ percent.")
    
    p.output(os.path.join(OUTPUT_DIR, "Enterprise_Strategy_Report.pdf"))

# ---------------------------------------------------------
# REPORT 3: AI Brain Plan
# ---------------------------------------------------------
def report_ai_brain_plan():
    title = "AI Brain Upgrade Implementation Plan"
    p = new_pdf()
    cover_page(p, "AI Brain Upgrade", "Primary Intelligence Engine Integration", "Moving from passive filtering to active orchestration.")
    
    new_page(p, title)
    section(p, "Proposed Capabilities")
    bullets(p, ["ARIA Persona: Expert Analyst Identity", "Chain-of-Thought reasoning for verification", "RunContextManager for live session memory", "Gap-Analysis for aggregator queries"])
    
    section(p, "Budget Estimates")
    table(p, ["Model", "Daily Cost", "Monthly (30d)"], [
        ["Gemini Flash", "$0.05", "$1.50"],
        ["Gemini Pro", "$0.60", "$18.00"],
        ["Total", "$0.65", "$19.50"]
    ])
    
    p.output(os.path.join(OUTPUT_DIR, "AI_Brain_Upgrade_Plan.pdf"))

if __name__ == "__main__":
    report_how_it_works()
    report_enterprise_strategy()
    report_ai_brain_plan()
    print("PDFs generated in docs/ folder.")
