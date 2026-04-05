# 🐚 Energy M&A Scraper: PowerShell Run Guide

This guide provides step-by-step instructions for running the Energy M&A Scraper using Windows PowerShell.

---

## 🏎️ Quick Start (The "Daily Run" Flow)

Follow these 3 steps to run a standard scrape:

### 1. Open PowerShell & Navigate
Press `Win + X` and select **Windows PowerShell** (or search for it in the Start menu). Then, copy and paste this command:

```powershell
cd "C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run"
```

### 2. Activate the Environment
You must activate the virtual environment so the script can access its dependencies (Playwright, BeautifulSoup, etc.):

```powershell
.\test_venv\Scripts\Activate.ps1
```

> [!TIP]
> If you see a red error saying **"execution of scripts is disabled on this system"**, run this command once to fix it:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. Run the Scraper
Run the main script with a start and end date (**Format: DD-MM-YYYY**):

```powershell
python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026
```

---

## 🛠️ Advanced Execution Modes

The scraper supports several flags to customize how it runs.

### 👁️ Visible Mode (For Troubleshooting)
Use this if you want to see the browser window while it works (useful for watching it bypass Cloudflare):
```powershell
python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026 --visible
```

### 🎯 Filtering Specific Sites
If you only want to check a few specific sources (e.g., Bloomberg and Reuters):
```powershell
python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026 --sites "Bloomberg,Reuters"
```

### ⚡ Parallel Workers
Increase speed by running more sites at once (default is 3):
```powershell
python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026 --workers 6
```

### 🔍 Historical Lookback
By default, the script looks back 2 days before your `--start` date to catch "late" news. You can change this:
```powershell
python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026 --lookback 5
```

---

## 📈 Alternative Ways to Run

### Option A: The "One-Liner"
You can combine navigation, activation, and execution into a single line for extreme speed:
```powershell
cd "C:\Users\harsh\OneDrive\Desktop\Scraper Trial Run"; .\test_venv\Scripts\Activate.ps1; python energy_scraper\main.py --start 28-03-2026 --end 30-03-2026
```

### Option B: Onboarding New Sites
To use the automated onboarding agent for a new URL:
```powershell
python energy_scraper\onboard_site.py --url "https://newsite.com/news" --name "My New Site"
```

---

## 📂 Where is the Data?
After running, your results will be saved in:
1. **Excel Report**: `energy_scraper/Energy_MA_Report_Async_[TIMESTAMP].xlsx`
2. **Logs**: `energy_scraper/logs/scraper_[TIMESTAMP].log`
3. **Database**: `energy_scraper/deals.db` (The persistent deduplication brain)
