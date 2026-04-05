# Energy M&A Scraper — Architecture & Context Handoff

**Project Goal**: A high-accuracy, async Python web scraper that extracts Energy Sector Mergers & Acquisitions (M&A) deals from 30+ heavily protected industry news sites and wire services, outputting them into a styled, multi-sheet Excel report.

## 🏗️ Core Architecture & Pipeline
The project uses a pure asynchronous pipeline (`asyncio`, `aiohttp`) to maximize throughput. 
The data flow is:
1. **Target Identification (`config.py`)**: 30+ sites defined with `url`, `rss_url`, `needs_js`, and crucially, `google_news_queries` (to bypass heavy JS/bot-protection on wire services).
2. **Smart Fetching (`fetcher.py`)**: An async waterfall strategy: 
   `RSS -> Google News RSS (for wire services) -> Playwright (JS rendering) -> CloudScraper (bypass Cloudflare) -> AIOHTTP -> Google News fallback`. 
   *Note: Bot-blocked sites like Bloomberg fall back to parsing the URL slug for the headline.*
3. **Keyword & Relevance Filtering (`scraper.py`)**: Headlines and body text are scored using a keyword regex system (`config.py`). Multi-lingual keywords (Ukrainian, French, German, Spanish) are included to catch international deals.
4. **AI Deal Verification Gate (`ai_extractor.py`)**: A 2-Phase verification using **Groq** (`llama-3.1-8b-instant`). 
   - *Phase 1:* Scans headline + body (crucial for catching M&A deals hidden in "Earnings Reports").
   - *Phase 2 (Cross-Check):* If the AI rejects a headline, it automatically queries Google News. If ≥2 independent sources confirm the deal, the AI rejection is overridden.
   - *Groq limits are handled via a strict 4.5s asyncio.Lock (~13 RPM) to prevent 429 Too Many Requests errors.*
5. **Excel Export (`excel_writer.py`)**: Uses `pandas` and `openpyxl` to generate a 6-sheet report: Output, Review Queue, Rejected by AI, Website Processing Log, Issues, and Dashboard.

## 🚨 CRITICAL FIXES (DO NOT REVERT THESE)
If you ask an AI to refactor or fix the scraper, **make sure it doesn't break these battle-tested features**:
- **Groq Rate Limiting**: `ai_extractor.py` uses `await asyncio.sleep(4.5 - elapsed)` inside an `asyncio.Lock()`. Do not remove this or Groq will throw `429` errors.
- **Wire Service Fetching**: BusinessWire, PRNewswire, and GlobeNewswire rely heavily on `fetch_google_news_rss_raw()` looping over `google_news_queries`. Do not replace this with raw HTML scraping, as their JS-rendered pages and paywalls will block you and drop valid deals.
- **Bot-Blocker URL Slug Parsing**: If `fetch_static()` gets an "Are you a robot?" headline, `scraper.py` parses the URL slug (e.g., `form-energy-sells-batteries...`) to extract the deal. Do not remove this fallback mechanism.
- **Date Parsing**: Date parsing relies on `date_parser.py` and `dateparser`. `scraper.py` handles `None` dates by defaulting them to the `start_date` so they aren't accidentally filtered out.

## 🛠️ Tech Stack & Requirements
- **Python Version**: 3.10+
- **Core Libraries**: `aiohttp`, `beautifulsoup4`, `feedparser`, `cloudscraper`, `playwright`, `playwright-stealth`, `groq`, `pandas`, `openpyxl`, `python-dotenv`, `dateparser`.
- **API Keys Needed**: `.env` file requires `GROQ_API_KEY`.

## 🚀 How to Run
```powershell
# 1. Ensure Playwright browsers are installed
playwright install chromium

# 2. Run the main async scraper (adjust dates as needed)
python main.py --start "23-03-2026" --end "24-03-2026" --workers 4
```
