# 🚀 Energy M&A Scraper: Automated Site Onboarding Guide

The **Automated Site Onboarder** (`onboard_site.py`) is an agentic tool designed to add new sources to the scraper without requiring manual code changes to `config.py`. It benchmarks a new URL, determines the required rendering engine (Static vs Playwright JS), tests headline extraction, and persists the configuration.

---

## 🛠️ Basic Usage

To onboard a single website, run the following command in your terminal:

```bash
python onboard_site.py --url "https://example-energy-news.com/latest" --name "Example Energy News"
```

### What Happens Internally?
1. **Connectivity Check**: Pings the URL via standard HTTP to check for `200 OK`.
2. **Bot Detection**: Identifies Cloudflare, "Please Enable JS", or 403 Forbidden errors to decide if `needs_js: True` is required.
3. **DOM Heuristics**: Scans the page for standard article patterns (H2/H3 tags inside anchors) to verify that the site is scrapable.
4. **Auto-Injection**: Generates a JSON configuration block and appends it to `dynamic_sites.json`.

---

## 📂 Testing Multiple Links in Batch

If you have a list of URLs, you can batch process them using a simple PowerShell loop:

### PowerShell (Windows)
```powershell
$sites = @(
    @{url="https://site1.com/news"; name="Site One"},
    @{url="https://site2.com/latest"; name="Site Two"}
)

foreach ($site in $sites) {
    python onboard_site.py --url $site.url --name $site.name
}
```

---

## 🧩 How it Integrates
You do **not** need to edit `config.py`. 
We have modified `config.py` to automatically look for a file named `dynamic_sites.json` in the same directory. If that file exists, its contents are merged into the main `TARGET_SITES` list at runtime.

### Configuration Hierarchy
1. **`config.py`**: Hardcoded high-priority enterprise sources.
2. **`dynamic_sites.json`**: Dynamically added sources via the Onboarder (Loaded automatically).

---

## 🔍 Troubleshooting

### 1. Site added but no deals found?
- Check if the site requires a custom selector for headlines. The onboarder uses a **Universal Heuristic** which works for 90% of news sites, but some complex React/Vue apps might need a manual tweak in the `dynamic_sites.json` file.
- Check `logs/` to see if the site is being blocked during the actual run.

### 2. "Playwright JS mode required"
- This is normal for modern sites. The onboarder will automatically set `"needs_js": true` so the main scraper knows to use the Stealth Browser engine.

### 3. Duplicates
- The onboarder automatically deduplicates by URL. If you run the same URL twice, it will update the existing entry rather than creating a new one.

---

> [!IMPORTANT]
> Always run a **Lookback Test** after onboarding a new site to ensure it's pulling data correctly:
> `python main.py --lookback 1 --site "Site Name"`
