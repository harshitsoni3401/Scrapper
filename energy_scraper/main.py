"""
main.py — Enterprise CLI entry point for the Energy M&A Scraper.

Sets up logging, parses arguments, and launches the parallel scraper.
"""

import argparse
import logging
import sys
import os
from datetime import datetime
import asyncio
import urllib.request
import json

try:
    from .scraper import AsyncMAScraper
    from .project_paths import ENV_FILE, GOOGLE_CREDENTIALS_PATH, LOGS_DIR, ensure_runtime_dirs
except ImportError:
    from scraper import AsyncMAScraper
    from project_paths import ENV_FILE, GOOGLE_CREDENTIALS_PATH, LOGS_DIR, ensure_runtime_dirs

def configure_console_output():
    """Prefer UTF-8 console output on Windows so status lines do not crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def setup_logging():
    """Configure structured logging to both file and console."""
    ensure_runtime_dirs()
    log_file = LOGS_DIR / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    # Suppress noisy third-party INFO spam
    logging.getLogger("readability.readability").setLevel(logging.ERROR)  # hides 'ruthless removal did not work'
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hides every HTTP OK line
    logging.getLogger("feedparser").setLevel(logging.WARNING)  # hides deprecation warnings
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
    return log_file

async def main_async():
    configure_console_output()
    parser = argparse.ArgumentParser(
        description="Energy-Sector M&A Scraping Agent (Enterprise/Parallel Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --start 22-03-2026 --end 25-03-2026
  python main.py --start 22-03-2026 --end 25-03-2026 --visible --workers 5
        """,
    )
    parser.add_argument("--start", type=str, required=True,
                        help="Start date (DD-MM-YYYY)")
    parser.add_argument("--end", type=str, required=True,
                        help="End date (DD-MM-YYYY)")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode (for CAPTCHAs)")
    parser.add_argument("--workers", type=int, default=3, help="Number of concurrent site workers")
    parser.add_argument("--no-aggregator", action="store_true", help="Disable the news aggregation layer")
    parser.add_argument("--sites", type=str, default=None,
                        help="Comma-separated site name filter (partial match). "
                             "Example: --sites 'Bloomberg,Reuters,AccessNewswire'")
    parser.add_argument("--lookback", type=int, default=2, 
                        help="Days to look back before start date (default 2) to catch missed deals.")
    
    args = parser.parse_args()

    # Convert incoming DD-MM-YYYY strings to scraper's expected YYYY-MM-DD
    from datetime import timedelta
    start_input = (args.start or "").strip().strip('"').strip("'")
    end_input = (args.end or "").strip().strip('"').strip("'")
    try:
        start_obj = datetime.strptime(start_input, "%d-%m-%Y")
        actual_start_obj = start_obj - timedelta(days=args.lookback)
        s_date = actual_start_obj.strftime("%Y-%m-%d")
        e_date = datetime.strptime(end_input, "%d-%m-%Y").strftime("%Y-%m-%d")
        
        if args.lookback > 0:
            print(f"  📅 1-Day Lookback engaged: Scraping from {s_date} to {e_date} to capture latent news.")
    except ValueError as exc:
        print(
            "ERROR: Dates must be in DD-MM-YYYY format "
            f"(received start={start_input!r}, end={end_input!r}; {exc})"
        )
        sys.exit(1)

    log_file = setup_logging()
    
    # Pre-run diagnostics
    print(f"\n{'='*70}")
    print("  Initializing Dependency Checks…")
    
    has_playwright = False
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth
        has_playwright = True
    except ImportError:
        pass

    has_rss = False
    try:
        import feedparser
        has_rss = True
    except ImportError:
        pass
        
    has_aiohttp = False
    try:
        import aiohttp
        has_aiohttp = True
    except ImportError:
        pass

    print("  Dependencies:")
    print(f"  {'✅' if has_playwright else '❌'} Playwright — JS rendering enabled")
    print(f"  {'✅' if has_rss else '❌'} feedparser — RSS feed support enabled")
    print(f"  {'✅' if has_aiohttp else '❌'} aiohttp — Async requests enabled")
    
    import cloudscraper
    print(f"  ✅ CloudScraper — Anti-bot fallback enabled")
    print(f"{'='*70}")

    # ── API Key Status Check ──
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_FILE)

    print(f"\n{'='*70}")
    print("  🔑 API Key Status Check")
    print(f"{'='*70}")

    # Check Groq key
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=3,
            )
            print(f"  ✅ GROQ_API_KEY      — Working (model: llama-3.1-8b-instant)")
        except Exception as e:
            err = str(e)[:80]
            print(f"  ❌ GROQ_API_KEY      — FAILED: {err}")
    else:
        print(f"  ⚠️  GROQ_API_KEY      — Not set")

    # Check extra Groq keys
    for i in range(2, 6):
        extra_key = os.environ.get(f"GROQ_API_KEY_{i}", "")
        if extra_key:
            try:
                from groq import Groq
                client = Groq(api_key=extra_key)
                resp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": "Say OK"}],
                    max_tokens=3,
                )
                print(f"  ✅ GROQ_API_KEY_{i}    — Working")
            except Exception as e:
                err = str(e)[:80]
                print(f"  ❌ GROQ_API_KEY_{i}    — FAILED: {err}")

    # Check Gemini key
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            req = urllib.request.Request(test_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"  ✅ GEMINI_API_KEY    — Working")
                else:
                    print(f"  ❌ GEMINI_API_KEY    — HTTP {resp.status}")
        except Exception as e:
            err = str(e)[:80]
            print(f"  ❌ GEMINI_API_KEY    — FAILED: {err}")
    else:
        print(f"  ⚠️  GEMINI_API_KEY    — Not set")

    # ── Google Sheets Check ──
    gs_exists = GOOGLE_CREDENTIALS_PATH.exists()
    print(f"  {'✅' if gs_exists else '❌'} GOOGLE_SHEETS    — {'Credentials Found' if gs_exists else 'Missing'}")
    
    print(f"{'='*70}\n")
    
    # ── Site Filter ──
    site_filter = None
    if args.sites:
        site_filter = [s.strip().lower() for s in args.sites.split(",") if s.strip()]
        print(f"  🔍 Site filter active: {site_filter}")

    scraper = AsyncMAScraper(
        start_date=s_date,
        end_date=e_date,
        headless=not args.visible,
        max_workers=args.workers,
        enable_aggregator=not args.no_aggregator,
        site_filter=site_filter,
    )
    
    await scraper.run()
    print(f"\n✅ Pipeline Finished. Run Logs saved to: {log_file}")

def main():
    import asyncio
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
