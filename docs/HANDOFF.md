# Project Handoff: Energy M&A Scraper (v3.0 -> v4.0)

## 📌 Project Status Overview
- **Version**: 3.0 ("Enterprise Master")
- **Rating**: 9.4/10 (Top-tier engineering, pending strict sector filtering)
- **Primary Goal**: 100% Recall and High Precision for Energy M&A deals.
- **Current Blocker**: False positives in "GPU", "HVAC", and "Market Reports" (to be fixed in v4.0).

## 🛠️ Infrastructure & Environment
- **Workspace**: `c:\Users\harsh\OneDrive\Desktop\Scraper Trial Run`
- **Active Environment**: `test_venv` (Activate via `.\test_venv\Scripts\Activate.ps1`)
- **Key Files**:
    - `main.py`: Entry point for the pipeline.
    - `energy_scraper/scraper.py`: Core logic for site crawling and section discovery.
    - `energy_scraper/ai_extractor.py`: The heart of the AI verification and translation engine.
    - `energy_scraper/config.py`: Site configurations and (formerly) keyword filters.
    - `energy_scraper/browser.py`: Stealth playwright engine with CAPTCHA audio alert.

## 🚀 Key Achievements (v1.0 - v3.0)
1. **Multi-Model Rotation**: Rotates through 10+ Groq keys and 3 models (Llama 3.1, 3.3, 4-Scout) to bypass rate limits.
2. **"Greedy" JSON Parser**: Native regex-based JSON extraction that handles conversational "chatter" from LLMs.
3. **Audio-Handover**: Single 900Hz tone to alert the user for manual CAPTCHA solving.
4. **Multilingual Support**: Full-body translation for Russian sources (Neftegaz.ru).
5. **Self-Learning Memory**: `deal_memory.json` stores known companies and user-corrected results to improve future AI prompts.

## 🚨 Final Objective: v4.0 "AI-Native Filter"
The user has requested to **scrap keyword-based "Literal" filters** and move to a fully **AI-driven rejection logic**.
- **The Issue**: Keywords like "Pipeline" trigger false positives for "GPU Infrastructure Pipeline".
- **The Solution**: Enhance the AI's "Sector Awareness". The AI must now explicitly classify the sector (e.g., HVAC vs Energy) and self-reject if it doesn't meet the "Energy/Mining" criteria.

## 📋 Running the Pipeline
```powershell
.\test_venv\Scripts\Activate.ps1
python energy_scraper/main.py --start "23-03-2026" --end "30-03-2026" --workers 4 --visible
```

## 📩 Handoff Note for Next Agent:
> "Continue the v4.0 upgrade by removing Python-level keyword filters and reinforcing the AI system prompt with the 'Negative Examples' found in the March 30 Audit (specifically GPU/HVAC/Cement/Market Reports)."
