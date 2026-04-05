import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Ensure we can import from the repo root no matter where the script is run from
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from energy_scraper.scraper import AsyncMAScraper
from energy_scraper.config import TARGET_SITES

async def verify_fixes():
    # Setup dates for last 48h
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    print(f"--- VERIFICATION RUN: {start_date} to {end_date} ---")
    
    # Test specific formerly failing sites
    test_sites_names = ["BusinessWire - Energy", "Neftegaz.ru", "SEC EDGAR - S-1", "AccessNewswire - Oil Gas & Energy"]
    
    scraper = AsyncMAScraper(
        start_date=start_date,
        end_date=end_date,
        headless=True, 
        max_workers=1, # Single worker for clean logging and verification
        enable_aggregator=False,
        site_filter=test_sites_names
    )
    
    await scraper.run()
    
    print("\n--- RESULTS ---")
    for deal in scraper.deals:
        print(f"✅ Found Deal: [{deal['Source']}] {deal['Headline'][:60]}...")
    
    for issue in scraper.issues:
        print(f"❌ Issue: [{issue[3]}] {issue[2]}")

if __name__ == "__main__":
    asyncio.run(verify_fixes())
