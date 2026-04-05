# Energy M&A Scraper

Async Python pipeline for collecting and validating energy-sector M&A deals across curated news, wire, and filing sources.

## What This Repo Does

- Scrapes curated energy and finance sources
- Falls back across RSS, Google News RSS, CloudScraper, and Playwright
- Uses Groq/Gemini-backed AI verification and extraction
- Writes multi-sheet Excel output with review and rejection queues
- Supports Google Sheets feedback ingestion

## PowerShell Quick Start

1. Open PowerShell.
2. Change into the project folder:

```powershell
cd "C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run - Codex"
```

3. Create the working environment and install dependencies:

```powershell
.\scripts\Setup.ps1
```

4. Create your `.env` file from the example and fill in the required keys:

```powershell
copy .env.example .env
```

5. Run the local project checks:

```powershell
.\scripts\Test-Project.ps1
```

6. Run a narrow live scrape:

```powershell
.\scripts\Run-Scraper.ps1 -Start "31-03-2026" -End "01-04-2026" -Workers 1 -Sites "BusinessWire - Energy" -NoAggregator
```

## Browser-Only Mode (Playwright Rendering Only)

If you want to force browser rendering for **all** sites and disable RSS/Google-News/CloudScraper/aiohttp fallbacks:

```powershell
python -m energy_scraper.main --start "31-03-2026" --end "01-04-2026" --workers 1 --browser-only
```

## Direct Python Commands

If you prefer not to use the helper scripts:

```powershell
cd "C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run - Codex"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m energy_scraper.main --start "31-03-2026" --end "01-04-2026" --workers 1 --sites "BusinessWire - Energy" --no-aggregator
```

## Environment Setup

Recommended:

- `GROQ_API_KEY` for AI verification and extraction
- `GEMINI_API_KEY` for grounding fallback
- `SPREADSHEET_ID` if you want Google Sheets enabled without create/quota issues

Optional:

- `GROQ_API_KEY_2` to `GROQ_API_KEY_4`
- `NEWSFILTER_EMAIL`
- `NEWSFILTER_PASSWORD`

Without `GROQ_API_KEY` and `GEMINI_API_KEY`, the scraper still runs, but AI-assisted deal verification is disabled.

## Budget Mode (Lower Token Use)

Set `AI_BUDGET_MODE=1` in `.env` to reduce AI usage:

- Shorter AI prompts and smaller body snippets
- Skips optional AI agents (self-healing selectors, query generation, QA review)
- Keeps the core verification/extraction pipeline active

This is the recommended mode when you want to conserve credits and keep the run lightweight.

## Future Vertex Pipeline

`VERTEX_API_KEY` is a placeholder for a future Google Vertex AI pipeline. It is not used yet and does not affect current runs.

## Output Locations

- Use `python -m energy_scraper.main` from the repo root for the most reliable import behavior.
- Excel reports are written to `reports\runs\`.
- Logs are written to `reports\logs\`.
- Review feedback files are written to `reports\feedback\`.
- The old `test_venv` is still present as a legacy environment, but `.venv` is the recommended standard going forward.

## Troubleshooting

- If Google Sheets fails during startup, add `SPREADSHEET_ID` and share that sheet with the service-account email from `google_credentials.json`.
- If a site needs browser rendering, run `.\scripts\Setup.ps1` once so Playwright Chromium is installed in `.venv`.
- If PowerShell execution policy blocks scripts, run `Set-ExecutionPolicy -Scope Process Bypass` in the current shell and retry.
