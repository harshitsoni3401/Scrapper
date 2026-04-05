"""
db_manager.py — Local SQLite state tracking for Energy M&A Scraper.
Provides a persistent "memory" of scraped deals to avoid re-scraping
if they appear on different PR wires hours apart.
"""

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent / "deals.db"

class DealDatabase:
    def __init__(self, db_path=_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deals (
                    deal_hash TEXT PRIMARY KEY,
                    headline TEXT,
                    url TEXT,
                    buyer TEXT,
                    seller TEXT,
                    asset TEXT,
                    value TEXT,
                    status TEXT,
                    date_discovered TEXT
                )
            ''')
            conn.commit()

    def _generate_hash(self, headline: str) -> str:
        """Create a consistent hash from the headline."""
        clean = ''.join(e for e in headline.lower() if e.isalnum())
        return hashlib.md5(clean.encode('utf-8')).hexdigest()

    def deal_exists(self, headline: str) -> bool:
        """Check if a deal was already processed based on its headline hash."""
        dh = self._generate_hash(headline)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM deals WHERE deal_hash = ?', (dh,))
            return cursor.fetchone() is not None

    def insert_deal(self, deal: dict):
        """Insert a newly processed deal into the database."""
        headline = deal.get("Headline", "")
        if not headline:
            return

        dh = self._generate_hash(headline)
        dt = datetime.now().isoformat()

        def _to_str(val):
            if isinstance(val, list):
                return ", ".join(str(v) for v in val if v)
            return str(val) if val else "Unknown"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO deals 
                (deal_hash, headline, url, buyer, seller, asset, value, status, date_discovered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                dh,
                headline,
                deal.get("URL", ""),
                _to_str(deal.get("Buyer", "Unknown")),
                _to_str(deal.get("Seller", "Unknown")),
                _to_str(deal.get("Asset/Target", "")),
                _to_str(deal.get("Deal Value", "Undisclosed")),
                "Announced",
                dt
            ))
            conn.commit()
