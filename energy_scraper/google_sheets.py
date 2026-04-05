"""
google_sheets.py — Google Sheets synchronization layer for the Energy M&A Scraper.

Handles:
  • Authentication via Service Account JSON
  • Sheet creation and header row management
  • Appending new deals while avoiding duplicates (via URL check)
  • Maintaining both a Master Database and industry-specific tabs
"""

import logging
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logger = logging.getLogger("energy_scraper.google_sheets")

# Scopes required for Sheets and Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSheetsManager:
    def __init__(self, credentials_path: str = "google_credentials.json", spreadsheet_name: str = "Energy M&A Master Database"):
        self.credentials_path = credentials_path
        self.spreadsheet_name = spreadsheet_name
        self.spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip().strip('"').strip("'")
        self.client = None
        self.spreadsheet = None
        self.enabled = False
        self._authenticate()

    def _authenticate(self):
        try:
            if not getattr(self, "credentials_path") or not isinstance(self.credentials_path, str):
                logger.warning("Google credentials path not provided.")
                return

            if not os.path.exists(self.credentials_path):
                logger.warning(f"Google credentials file not found at: {self.credentials_path}")
                return

            creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            self.enabled = True
            logger.info("Successfully authenticated with Google Sheets API.")
        except Exception as e:
            logger.error(f"Google Sheets authentication failed: {e}")
            self.enabled = False

    def _get_or_create_spreadsheet(self):
        if not self.enabled:
            return None
        
        try:
            # 1. Prioritize Spreadsheet ID if provided (avoids create quota issues)
            if self.spreadsheet_id:
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                logger.info(f"Opened spreadsheet by ID: '{self.spreadsheet_id}'")
            else:
                # 2. Try to open by name
                self.spreadsheet = self.client.open(self.spreadsheet_name)
                logger.info(f"Opened existing spreadsheet by name: '{self.spreadsheet_name}'")
        except Exception as e:
            if not self.spreadsheet_id:
                try:
                    # 3. Last resort: Create new (fails if service account quota full)
                    logger.warning(f"Spreadsheet not found, attempting to create: {e}")
                    self.spreadsheet = self.client.create(self.spreadsheet_name)
                    logger.info(f"Created new spreadsheet: '{self.spreadsheet_name}'")
                    print(f"\n📢  NEW GOOGLE SHEET CREATED: '{self.spreadsheet_name}'")
                    print(f"🔗  URL: {self.spreadsheet.url}\n")
                except Exception as create_err:
                    err_text = str(create_err)
                    logger.error(f"Failed to create spreadsheet: {err_text}")
                    print("\n[ERROR] GOOGLE SHEETS: Could not open or create the configured sheet.")
                    if "drive api" in err_text.lower():
                        print("[FIX] Enable the Google Drive API for the service account project, then retry.")
                    print("[FIX] Create a blank sheet in your Google Drive, share it with the service account email, and set SPREADSHEET_ID in your .env file.\n")
                    self.enabled = False
                    return None
                    print("\n❌  GOOGLE SHEETS ERROR: Could not create sheet (Drive Quota Exceeded).")
                    print("👉  FIX: Create a blank sheet in your personal Google Drive, share it with the service account email, and add 'SPREADSHEET_ID=your_id_here' to your .env file.\n")
                    self.enabled = False
                    return None
            else:
                logger.error(f"Could not open spreadsheet with ID '{self.spreadsheet_id}': {e}")
                self.enabled = False
                return None
        
        return self.spreadsheet

    def _prepare_sheet(self, sheet_name: str, headers: list):
        """Ensures a worksheet exists and has the correct headers."""
        try:
            ws = self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols=str(len(headers) + 2))
            ws.append_row(headers)
            # Freeze header
            ws.freeze(rows=1)
            logger.info(f"Created worksheet '{sheet_name}' with headers.")
        return ws

    def sync_deals(self, deals: list):
        """
        Sync current run's deals to the Google Spreadsheet.
        Appends to a 'Master Database' and industry-specific sheets.
        """
        if not self.enabled or not deals:
            return

        ss = self._get_or_create_spreadsheet()
        if not ss:
            return

        # Define headers (matches Excel output)
        headers = [
            "Headline", "Buyer", "Seller", "Asset", "Date", "Industry", 
            "Sector", "Link", "County", "Value (USD)", "Deal Type", 
            "Confidence", "Source", "Sheet Category", "Sync Date"
        ]

        # 1. Sync to Master Database
        master_ws = self._prepare_sheet("Master Database", headers)
        self._append_new_deals(master_ws, deals)

        # 2. Sync to Industry Sheets
        industry_groups = {}
        for d in deals:
            sheet_name = d.get("Sheet", "P&U")
            if sheet_name not in industry_groups:
                industry_groups[sheet_name] = []
            industry_groups[sheet_name].append(d)

        for sheet_name, group_deals in industry_groups.items():
            if sheet_name == "Reports":
                # Special layout for reports
                rpt_headers = ["Headline", "Link", "Date", "Sync Date"]
                ws = self._prepare_sheet("Reports", rpt_headers)
                self._append_new_deals(ws, group_deals, is_report=True)
            else:
                ws = self._prepare_sheet(sheet_name, headers)
                self._append_new_deals(ws, group_deals)

        # 3. Create/Prepare Feedback Sheet (as requested by user)
        feedback_headers = ["Feedback to AI", "Comments", "Headline", "Link", "Sync Date"]
        self._prepare_sheet("AI Learning & Feedback", feedback_headers)

        logger.info(f"Sync complete for {len(deals)} deals.")

    def get_feedback_data(self) -> list[str]:
        """
        Fetch all feedback entries from the 'AI Learning & Feedback' sheet.
        Returns a list of strings combining 'Feedback to AI' and 'Comments'.
        """
        if not self.enabled:
            return []
        
        ss = self._get_or_create_spreadsheet()
        if not ss:
            return []
        
        try:
            ws = self.spreadsheet.worksheet("AI Learning & Feedback")
            data = ws.get_all_records()
            feedback_list = []
            for row in data:
                # Combine "Feedback to AI" and "Comments" into a single lesson
                parts = []
                if row.get("Feedback to AI"): parts.append(str(row["Feedback to AI"]))
                if row.get("Comments"): parts.append(str(row["Comments"]))
                
                if parts:
                    lesson = " ".join(parts).strip()
                    if lesson:
                        feedback_list.append(lesson)
            
            logger.info(f"Fetched {len(feedback_list)} shared feedback entries from Google Sheets.")
            return feedback_list
        except Exception as e:
            logger.warning(f"Could not fetch feedback from Google Sheets: {e}")
            return []

    def _append_new_deals(self, ws, deals: list, is_report: bool = False):
        """Append deals if their Link is not already in the worksheet."""
        try:
            existing_urls = set(ws.col_values(headers_map(ws, "Link")))
        except Exception:
            existing_urls = set()

        sync_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows_to_add = []

        for d in deals:
            url = d.get("Link", "")
            if url and url not in existing_urls:
                if is_report:
                    row = [
                        d.get("Headline", ""),
                        d.get("Link", ""),
                        d.get("Date", ""),
                        sync_time
                    ]
                else:
                    row = [
                        d.get("Headline", ""),
                        d.get("Buyer", ""),
                        d.get("Seller", ""),
                        d.get("Asset", ""),
                        d.get("Date", ""),
                        d.get("Industry", ""),
                        d.get("Sector", ""),
                        d.get("Link", ""),
                        d.get("County", ""),
                        d.get("Value", ""),
                        d.get("Deal Type", ""),
                        d.get("Confidence", ""),
                        d.get("Source", ""),
                        d.get("Sheet", ""),
                        sync_time
                    ]
                rows_to_add.append(row)
                existing_urls.add(url) # Prevent duplicates WITHIN the same run if any

        if rows_to_add:
            ws.append_rows(rows_to_add)
            logger.info(f"Appended {len(rows_to_add)} new entries to '{ws.title}'")

def headers_map(ws, target_header: str) -> int:
    """Find the 1-based index of a header column."""
    try:
        headers = ws.row_values(1)
        return headers.index(target_header) + 1
    except ValueError:
        # Default fallback guesses if header row is missing or being created
        mapping = {"Link": 8 if "Master" in ws.title else 2}
        return mapping.get(target_header, 1)
