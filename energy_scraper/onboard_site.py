import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import aiohttp
except ImportError:
    print("Please install aiohttp first.")
    sys.exit(1)

# Ensure dynamic_sites_path points to the energy_scraper directory
_dynamic_sites_path = Path(__file__).parent / "dynamic_sites.json"

async def test_and_onboard_site(url: str, name: str):
    print(f"\n🚀 Phase 1: Initiating ping for {name} ({url})...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    html_content = ""
    needs_js = False
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    html_content = await resp.text()
                    print("✅ HTTP 200 OK — Standard request passed.")
                else:
                    print(f"⚠ HTTP {resp.status} — Likely blocked. Playwright JS mode required.")
                    needs_js = True
        except Exception as e:
            print(f"⚠ Request failed ({e}). Playwright JS mode required.")
            needs_js = True

    if "cloudflare" in html_content.lower() or "please enable js" in html_content.lower() or "forbidden" in html_content.lower():
        print("⚠ Cloudflare / Anti-Bot detected. Upgrading to Playwright JS mode.")
        needs_js = True

    print("\n🕵️ Phase 2: Analyzing DOM heuristics...")
    soup = BeautifulSoup(html_content, "html.parser") if html_content else None
    
    articles = []
    if soup:
        # Common structural heuristics
        for a_tag in soup.find_all("a", href=True):
            h_tag = a_tag.find(["h1", "h2", "h3", "h4"])
            if h_tag:
                text = h_tag.get_text(strip=True)
            else:
                text = a_tag.get_text(strip=True)
                
            if len(text) > 40 and " " in text:
                articles.append(text)
                if len(articles) >= 5:
                    break
                    
    if articles:
        print(f"✅ Heuristics confirmed! Found {len(articles)} potential article headlines.")
        for i, a in enumerate(articles, 1):
            print(f"   {i}. {a[:60]}...")
    else:
        print("⚠ Standard heuristics failed. The browser engine will use generic extraction.")

    print("\n⚙️ Phase 3: Generating failproof configuration block...")
    
    site_config = {
        "name": name,
        "url": url,
        "needs_js": needs_js,
        "is_paywall": False,
        "max_pages": 3,
        "rss_url": None,
        "pagination_type": "next_link",  # Default scalable assumption
        "load_more_selector": None,
        "next_page_selector": "a.next, a[rel='next'], a[aria-label='Next']"
    }
    
    print("\n💾 Phase 4: Injecting natively into dynamic_sites.json...")
    
    existing_sites = []
    if _dynamic_sites_path.exists():
        try:
            with open(_dynamic_sites_path, "r", encoding="utf-8") as f:
                existing_sites = json.load(f)
        except json.JSONDecodeError:
            print("⚠ JSON corrupted, starting fresh.")
            existing_sites = []
            
    # Deduplicate
    existing_sites = [s for s in existing_sites if s["url"] != url]
    existing_sites.append(site_config)
    
    with open(_dynamic_sites_path, "w", encoding="utf-8") as f:
        json.dump(existing_sites, f, indent=4)
        
    print(f"🎉 Success! '{name}' is completely onboarded and will be active on the next run.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Site Onboarder")
    parser.add_argument("--url", required=True, help="The URL to start scraping from")
    parser.add_argument("--name", required=True, help="Human-readable name for the site")
    args = parser.parse_args()
    
    asyncio.run(test_and_onboard_site(args.url, args.name))
