import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from energy_scraper.config import TARGET_SITES

print(f'TOTAL SITES: {len(TARGET_SITES)}')

removed_urls = [
    "https://www.ogj.com/",
    "https://www.hartenergy.com/news/",  # old single-entry hart
    "https://www.bnamericas.com/en/tag/electric-power",
    "https://www.bnamericas.com/en/tag/oil--gas",
    "https://www.bnamericas.com/en/tag/mining--metals",
    "https://www.businesswire.com/newsroom/industry/financial-services-and-capital-markets",
    "https://www.globenewswire.com/Search",
    "https://www.oilandgas360.com/oil-gas/",
    "https://www.oilandgas360.com/oilfield-services/",
    "https://www.oilandgas360.com/energy-transition/",
    "https://www.energynewsbulletin.net/category/oil-gas",
    "https://renewablesnow.com/company-news/deals/",
    "https://renewablesnow.com/news/",
    "https://seenews.com/news/archive/2026",
    "https://www.renewableenergymagazine.com/",
    "https://newsfilter.io/latest/news",
    "https://www.rigzone.com/news/finance_and_investing/",
    "https://www.mercomindia.com/",
    "https://www.newswire.com/newsroom/business-bankruptcy",
    "https://www.newswire.com/newsroom/business-business-news",
    "https://www.newswire.com/newsroom/business-corporate-communications",
    "https://www.newswire.com/newsroom/business-mergers-acquisitions",
    "https://www.newswire.com/newsroom/government-energy",
    "https://www.newswire.com/newsroom/industries-mining",
]

active_urls = {site["url"] for site in TARGET_SITES}

print("\n=== REMOVAL CHECK ===")
for url in removed_urls:
    status = "STILL PRESENT [WARN]" if url in active_urls else "REMOVED OK [OK]"
    print(f"  {status}: {url[:70]}")

print("\n=== ALL ACTIVE SITES ===")
for i, s in enumerate(TARGET_SITES, 1):
    print(f"  {i:3}. {s['name']}")
