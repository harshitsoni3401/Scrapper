from fpdf import FPDF

class ExecutionGuidePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(20, 40, 100)
        self.cell(0, 10, 'Energy M&A Scraper - PowerShell Execution Guide', 0, 1, 'C')
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

    def code_block(self, code):
        self.set_font('Courier', '', 10)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(0, 5, code, 1, 'L', 1)
        self.ln(5)

def generate_guide():
    pdf = ExecutionGuidePDF()
    pdf.add_page()

    # Section 1: Navigation
    pdf.chapter_title("1. Navigating to the Project Directory")
    pdf.chapter_body(
        "Open PowerShell and navigate to the root folder of the project. "
        "Use the 'cd' (change directory) command followed by the full path in quotes if there are spaces."
    )
    pdf.code_block("cd \"C:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run\"")

    # Section 2: Environment Activation
    pdf.chapter_title("2. Activating the Environment")
    pdf.chapter_body(
        "For this project, use the 'test_venv' which contains all necessary dependencies. "
        "Run the activation script as follows:"
    )
    pdf.code_block(".\\test_venv\\Scripts\\Activate.ps1")

    # Section 3: Running the Core Scraper
    pdf.chapter_title("3. Running the Main Scraper")
    pdf.chapter_body(
        "The main entry point is now located inside the 'energy_scraper/' package. "
        "You must run the script using the correct path from the root directory."
    )
    pdf.code_block("python energy_scraper/main.py")

    # Section 4: Command Arguments (Execution Modes)
    pdf.chapter_title("4. Customizing the Execution")
    pdf.chapter_body(
        "The scraper supports several arguments to control the date range and performance. "
        "All dates should be in DD-MM-YYYY format."
    )
    
    pdf.chapter_body("- Standard Run (Scrape specific dates):")
    pdf.code_block("python energy_scraper/main.py --start \"25-03-2026\" --end \"30-03-2026\"")

    pdf.chapter_body("- High-Speed Run (Increase workers):")
    pdf.chapter_body("By default, the scraper uses multiple workers. Increasing this number speeds up scraping but may hit rate limits.")
    pdf.code_block("python energy_scraper/main.py --workers 8")

    pdf.chapter_body("- Debug Mode (Visible Browser):")
    pdf.chapter_body("If you want to see the Playwright browser window in action (useful for debugging):")
    pdf.code_block("python energy_scraper/main.py --visible")

    pdf.chapter_body("- Composite command Example:")
    pdf.code_block("python energy_scraper/main.py --start \"20-03-2026\" --end \"25-03-2026\" --workers 4 --visible")

    # Section 5: Troubleshooting
    pdf.chapter_title("5. Troubleshooting Commands")
    pdf.chapter_body(
        "- If you see 'ModuleNotFoundError', ensure 'test_venv' is activated.\n"
        "- If Playwright errors occur: playwright install chromium\n"
        "- If you see 'No such file': Double-check that you are in the root directory using 'ls'."
    )

    pdf.output("PowerShell_Execution_Guide.pdf")
    print("Execution Guide PDF generated: PowerShell_Execution_Guide.pdf")

if __name__ == "__main__":
    generate_guide()
