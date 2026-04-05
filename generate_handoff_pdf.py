import os
from fpdf import FPDF

class HandoffPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(20, 40, 100)
        self.cell(0, 10, 'Energy M&A Scraper - v4.0 Project Handoff', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 7, body.encode('latin-1', 'replace').decode('latin-1'))
        self.ln()

def generate_handoff():
    pdf = HandoffPDF()
    pdf.add_page()

    # Section 1: Overview
    pdf.chapter_title("1. Business Case & Current Status")
    pdf.chapter_body(
        "The project has evolved into a 'Peak Level' (v3.0) Agentic Scraper. It successfully "
        "monitors 34+ websites for M&A signals. CURRENT RATING: 9.4/10.\n\n"
        "The current version (v4.0) aims for 100% precision by transitioning from simple "
        "keyword-based filtering to a fully Agentic AI-Native Guardrail system."
    )

    # Section 2: Environment
    pdf.chapter_title("2. Environment Setup")
    pdf.chapter_body(
        "Workspace: c:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run\n"
        "Active VEnv: test_venv\n"
        "Activation: .\\test_venv\\Scripts\\Activate.ps1\n"
        "Dependencies: playwright, aiohttp, groq, pandas, openpyxl, winsound."
    )

    # Section 3: Architecture Highlights
    pdf.chapter_title("3. Architecture & Intelligence")
    pdf.chapter_body(
        "- Multi-Key Rotation: Handles up to 10 Groq API keys to maintain high RPM.\n"
        "- Greedy JSON Parser: Resilient to LLM 'noise' and conversational filler.\n"
        "- CAPTCHA Audio Alert: Single 900Hz tone for human-in-the-loop intervention.\n"
        "- Russian Translation: Full-body translation for international sources like Neftegaz.ru."
    )

    # Section 4: The v4.0 Shift (AI-Native)
    pdf.chapter_title("4. AI-Native Rejection (v4.0 Goal)")
    pdf.chapter_body(
        "Per user requirements, we are ELIMINATING literal keyword filters (e.g., 'Cement', 'GPU') "
        "and moving this logic into the AI System Prompt. The AI is now responsible for identifying "
        "non-energy sectors and operational news (e.g., drilling reports) that keywords might miss."
    )

    # Section 5: Recent Audit Lessons
    pdf.chapter_title("5. Audit Findings (March 30)")
    pdf.chapter_body(
        "Recent false positives identified for elimination:\n"
        "- GPU Infrastructure (Mistaken for Midstream pipelines).\n"
        "- Wholesale HVAC (Mistaken for Energy deal).\n"
        "- Green Cement Market Reports (Mistaken for Transaction).\n"
        "- Operational Well Drilling (Mistaken for Deal)."
    )

    pdf.output("Project_Handoff_v4.pdf")
    print("Project Handoff PDF generated: Project_Handoff_v4.pdf")

if __name__ == "__main__":
    generate_handoff()
