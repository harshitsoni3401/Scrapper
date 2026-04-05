import os
from fpdf import FPDF

class ReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(20, 40, 100)
        self.cell(0, 10, 'Energy M&A Scraper - Project Analysis Report', 0, 1, 'C')
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
        self.multi_cell(0, 7, body)
        self.ln()

def generate_report():
    pdf = ReportPDF()
    pdf.add_page()

    # Section 1: Project Overview
    pdf.chapter_title("1. Project Overview")
    pdf.chapter_body(
        "The 'Energy M&A Scraper' is a high-accuracy, asynchronous Python-based web scraper "
        "designed to monitor over 30 industry news sites and wire services for Mergers & Acquisitions (M&A) "
        "deals in the energy sector. It automates the entire process from data discovery to AI-driven verification "
        " and styled Excel reporting."
    )

    # Section 2: Core Architecture
    pdf.chapter_title("2. Core Architecture")
    pdf.chapter_body(
        "The project follows a pure asynchronous pipeline using 'asyncio' and 'aiohttp' for high throughput. "
        "Key components include:\n"
        "- Smart Fetching: A waterfall strategy (RSS -> Google News -> Playwright -> CloudScraper) to bypass bot protection.\n"
        "- AI Deal Verification: Uses Groq (Llama-3.1-8b) to extract deal details and verify relevance.\n"
        "- Data Storage: Uses SQLite for deal deduplication and tracking.\n"
        "- Reporting: Generates multi-sheet Excel reports and syncs to Google Sheets."
    )

    # Section 3: Important Python Scripts
    pdf.chapter_title("3. Important Python Scripts")
    pdf.chapter_body(
        "- main.py: The primary entry point for running the scraper.\n"
        "- energy_scraper/scraper.py: Contains the core scraping and keyword scoring logic.\n"
        "- energy_scraper/fetcher.py: Handles URL fetching with multiple fallback mechanisms.\n"
        "- energy_scraper/ai_extractor.py: Interfaces with LLMs (Groq) to extract deal information.\n"
        "- energy_scraper/excel_writer.py: Formats and saves the extracted data into Excel sheets.\n"
        "- energy_scraper/config.py: Centralized configuration for sites, keywords, and API settings."
    )

    # Section 4: Virtual Environments
    pdf.chapter_title("4. Virtual Environments & Setup")
    pdf.chapter_body(
        "There are two virtual environments in this project:\n"
        "1. .venv: This was the original environment but it became incomplete (missing activation scripts).\n"
        "2. test_venv: This is the fully functional environment containing all dependencies.\n\n"
        "Why two? The 'test_venv' was created as a stable resolution to the broken '.venv' folder, "
        "ensuring the scraper can run without environment errors."
    )

    # Section 5: Running Instructions
    pdf.chapter_title("5. How to Run the Project")
    pdf.chapter_body(
        "To run the scraper from PowerShell:\n"
        "1. Activate the environment: .\\test_venv\\Scripts\\Activate.ps1\n"
        "2. Install browsers (if first time): playwright install chromium\n"
        "3. Execute main script:\n"
        "   python energy_scraper/main.py --start \"25-03-2026\" --end \"29-03-2026\" --workers 4"
    )

    # Section 6: Evaluation & Improvements
    pdf.chapter_title("6. Evaluation & Improvements")
    pdf.chapter_body(
        "Project Score: 9/10 (Excellent Engineering)\n\n"
        "Strengths:\n"
        "- Robustness: Excellent fallback mechanisms for bot-blocked sites.\n"
        "- Intelligence: AI-driven verification significantly reduces false positives.\n"
        "- Reporting: Clean, multi-sheet Excel output with Audit summaries.\n\n"
        "Areas for Improvement:\n"
        "- Dependency Cleanup: Delete the broken '.venv' and rename 'test_venv' to '.venv' to follow standards.\n"
        "- Configuration: Move site lists from 'config.py' to a JSON/YAML file for easier maintenance.\n"
        "- UI: Consider a simple web dashboard using Streamlit (which is already in the venv) for visual monitoring."
    )

    pdf.output("Energy_MA_Project_Report.pdf")
    print("PDF Report generated: Energy_MA_Project_Report.pdf")

if __name__ == "__main__":
    generate_report()
