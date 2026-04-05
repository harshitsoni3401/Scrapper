# Flowchart Explanations — Plain English Guide for Your Director Presentation

> **How to use this:** Read each section before your meeting. The explanations are written in simple business language — no Python knowledge needed. The Q&A section at the end prepares you for every likely cross-question.

---

## FLOWCHART 1: "Energy M&A Scraper — End-to-End Pipeline"
*(The main top-to-bottom pipeline diagram)*

### What this diagram shows in one sentence:
**"This is the complete journey of how the system goes from pressing a button to producing a finished Excel report — automatically, without any human doing the work in between."**

---

### Full walkthrough — step by step, in plain English:

**Step 1 — "START: User runs main.py with date range + workers"**

Think of this like pressing the "start" button on a machine. The user types one command in the terminal (like a search bar) and tells the system:
- **Which dates** to look for deals (e.g., 30 March to 31 March 2026)
- **How many workers** to run at the same time (like having 3 staff members searching simultaneously instead of just 1)

👉 *If a director asks: "How do you start it?"* — Say: "You type one command, specify the date range, and the system does everything else automatically. No clicking, no manual searching."

---

**Step 2 — "config.py: loads 84 Target Sites"**

Before it starts searching the internet, the system opens its address book — a master list of 84 hand-picked, trusted news websites. This includes wire services like BusinessWire, trade publications like Natural Gas Intelligence, renewables news like RenewablesNow, and even US government SEC filings.

👉 *If a director asks: "How do you decide which websites to monitor?"* — Say: "We manually curated 84 of the most reliable and comprehensive energy and financial news sources. This list is our intellectual property — it took significant work to build and tune."

---

**Step 3 — "AsyncNewsAggregator: Fetch articles from all 84 sites concurrently"**

This is where the system starts reading the news. The key word is **"concurrently"** — meaning all 84 websites are being read at the **same time**, not one after another. 

Think of it like having 84 staff members each reading a different newspaper simultaneously, instead of one person who has to finish reading one, put it down, and pick up the next.

👉 *If a director asks: "How long does it take?"* — Say: "Because all 84 sources are read simultaneously, the entire process — 84 websites, hundreds of articles, AI analysis on each — takes just 25 to 40 minutes, as opposed to days of manual analyst work."

---

**Step 4 — Diamond: "Site Blocked by Cloudflare? YES / NO"**

This is the first decision point. Many major news sites (like Bloomberg, Reuters) use a security shield called Cloudflare that blocks automated programs — they only want real people reading their site, not software.

The system automatically detects this:
- **If the site has no block (NO path):** It uses a fast, simple method to read the article — like a quick direct phone call.
- **If the site IS blocked (YES path):** It activates the **Playwright Stealth Browser** — a hidden, disguised web browser that mimics real human browsing behaviour so perfectly that the security system cannot tell it apart from a real person.

👉 *If a director asks: "What if websites try to block you?"* — Say: "We built a two-lane system. For normal websites, we use a fast approach. For protected websites, the system automatically switches to an advanced stealth browser that looks indistinguishable from a real human visitor. The switch happens in milliseconds, completely automatically."

---

**Step 5 — "extractor.py: Clean HTML, extract article body text"**

When you open a news website, you see the article but you also see the header, the navigation menu, the adverts, the "you might also like" section, cookie banners, etc. None of that is useful. This step strips all of that away and keeps only the actual article text — like a smart highlighter that the grabs the relevant content on the page.

👉 *If a director asks: "How do you handle all the junk on web pages?"* — Say: "We use a specialised text extraction engine that isolates only the article body and discards everything else — menus, ads, boilerplate text. The AI only ever sees clean, relevant content."

---

**Step 6 — "Hard Reject Blocklist (Hotel, Pharma, Retail → REJECT)"**

This is the system's **first free filter**. Before the expensive AI is called, the system checks if the article is obviously nothing to do with energy. It has a list of phrases like "hotel", "pharmaceutical", "biotech", "restaurant chain", "fashion brand". If any of these appear, the article is thrown away immediately.

**Why is this important?** Every AI check costs time and potentially money. The blocklist saves both by discarding irrelevant content before it ever reaches the AI.

👉 *If a director asks: "What stops it from wasting time on irrelevant articles?"* — Say: "We have a hard blocklist of 50+ non-energy phrases. An article mentioning a hotel acquisition, a pharma deal, or a retail brand is automatically discarded in milliseconds — before any AI is involved. This saves time and eliminates false positives at zero cost."

---

**Step 7 — Diamond: "Passes blocklist? YES → AI / NO → DISCARD (0 API credits used)"**

This is the gate. If the article passed the blocklist (YES), it goes to the AI. If it failed (NO), it's discarded — and crucially, no API credits are spent. This is smart cost management.

---

**Step 8 — "Groq LLM verify_is_deal() + assign industry sheet"**

This is the **AI brain**. The system sends the article headline and a portion of the article body to a large language model (like a very specialised version of ChatGPT, but optimised for speed). The AI does two things in a single step:

1. **Reads the article** and decides: "Is this a genuine merger, acquisition, or deal? Or is it just a market commentary, analyst opinion, or price report?"
2. **If it IS a deal**, the AI also decides which industry category it belongs to: Upstream, Midstream, Power & Utilities, Joint Ventures, etc.

Both decisions happen in **one AI call** — so it's efficient.

👉 *If a director asks: "How do you ensure accuracy?"* — Say: "Every article is individually reviewed by a large language model that reasons through the content like an analyst would. It decides whether it's a genuine transaction and which category it belongs to. The AI's full reasoning is stored alongside every decision for auditability."

---

**Step 9 — Diamond: "Is it an M&A deal? NO → rejected_deals / YES → extract_deal()"**

Another gate. If the AI says it's NOT a deal (it's market commentary, a price report, a personnel announcement etc.), the article goes to a "rejected deals" log — with the AI's full reasoning recorded.

If the AI confirms it IS a deal, the system proceeds to extract the structured data.

---

**Step 10 — "extract_deal() — Buyer, Seller, Asset, Value, Geography"**

Once confirmed as a real deal, the AI extracts the key facts in a structured format:
- **Who is buying?** (Buyer)
- **Who is selling?** (Seller)
- **What are they buying?** (Asset / Target company)
- **For how much?** (Deal Value — automatically converted to US Dollars from any currency)
- **Where is it?** (Geography — country or region)

---

**Step 11 — "db_manager.py: Cache to SQLite deals.db"**

Every confirmed deal is saved to a permanent local database. This does two things:
1. **Prevents duplicates**: If the same deal appears in 5 different news sources, it only enters the report once.
2. **Free re-runs**: If you run the system again for the same date range, it pulls from this saved database instead of re-contacting the AI — so the second run is completely free.

---

**Step 12 — "excel_writer.py: Export to Excel Report"**

The final step. All confirmed deals are formatted and written into the Excel workbook — each deal on the correct sheet, with all fields filled in, colour-coded by sector.

---

## FLOWCHART 2: "Python Module Architecture — File Relationships"
*(The tree diagram showing all the Python files)*

### What this diagram shows in one sentence:
**"This is the organisational chart of the software — which file does what, and how they all connect to each other."**

---

### Plain-English breakdown of each "department":

Think of the project like a company. Each file is a department with a specific job.

| File Name | What It Is in Business Terms |
|---|---|
| **main.py** | The **CEO / Entry Point** — gives the startup order, sets the date range, fires everything up |
| **scraper.py** | The **Operations Director** — coordinates all departments, controls the flow. NOTHING runs without it |
| **config.py** | The **Intelligence Database** — holds the master list of 84 websites and all the rules |
| **fetcher.py** | The **Research Team** — goes and fetches articles from normal, unprotected websites |
| **browser.py** | The **Undercover Agent** — handles protected sites using a disguised stealth browser |
| **extractor.py** | The **Editor** — cleans up raw web pages and extracts just the article text |
| **ai_extractor.py** | The **AI Analyst** — the most important department. Verifies deals and classifies them |
| **news_aggregator.py** | The **Newsfeed Monitor** — specifically handles RSS feeds and Google News search queries |
| **db_manager.py** | The **Filing Room** — saves all confirmed deals to a permanent local database |
| **excel_writer.py** | The **Report Writer** — formats everything into the final Excel report |
| **agentic_agents.py** | The **QA & Audit Team** — does a final review of all accepted deals before the report is printed |

👉 *If a director asks: "What happens if you need to add a new data source tomorrow?"* — Say: "Because each file has a single responsibility, adding a new source is simply adding one entry to config.py — the address book. No other files need to change. It's like adding a new phone number to a contacts list."

---

## FLOWCHART 3: "AI Classification Engine — Decision Flow"
*(The 4-tier funnel diagram)*

### What this diagram shows in one sentence:
**"This is the quality control system — the four security checkpoints every article must pass before it is accepted as a genuine deal."**

---

### The 4 Tiers explained with real analogies:

**TIER 0 — Hard Reject Blocklist**

*Analogy:* Imagine a security guard at the door of an exclusive energy industry conference. He has a list: "No hotels, no pharma companies, no retail brands allowed." Anyone matching that list is turned away at the door immediately — no questions asked, no checking ID, no calling the manager.

In the system: If an article mentions "hotel acquisition" or "pharmaceutical merger" or "fashion brand buyout", it is discarded in milliseconds. **Zero AI cost. Zero time wasted.**

This is the most cost-efficient step — it eliminates roughly 30% of all incoming articles before any expensive processing.

---

**TIER 1 — Keyword Scorer**

*Analogy:* For articles that got past the door, a junior analyst does a quick scan: "Does this article use words like 'E&P company', 'pipeline', 'LNG terminal', 'solar farm', 'wind turbine'?" If yes, the article gets pre-tagged with the most likely category.

This uses pure code logic — fast, free, and reliable for obvious cases.

If the keyword scan is inconclusive (article could belong to multiple categories), it escalates to Tier 2.

---

**TIER 2 — Groq AI Verification (The Expert Analyst)**

*Analogy:* A senior analyst with deep M&A expertise reads the article in full and makes a judgment:

"Is this genuinely a merger, acquisition, or divestiture? Or is it just a news article discussing the energy market? Or a company reporting its quarterly earnings? Or two companies signing a simple supply contract?"

This is where the heavy intelligence happens. The AI uses "chain-of-thought" reasoning — meaning it explains its thinking step by step, just as a human analyst would.

**Crucially: in the same reading, the AI also decides which Excel sheet the deal belongs to** (Upstream, Midstream, Renewables, etc.) — this saves a second AI call.

If the AI says YES → deal is confirmed, data extracted.
If the AI says NO → article logged in the "Rejected by AI" sheet with full reasoning.

---

**TIER 3 — Cross-Check Rescue (The Safety Net)**

*Analogy:* What if the senior analyst was unsure? In businesses, you'd ask a second opinion. This tier does exactly that. If the AI is uncertain (a "soft rejection"), the system automatically checks Google News: "Are there 5 or more other news sources reporting the same transaction?" If yes, the deal is rescued and placed in the "Review Queue" for a human analyst to make the final call.

---

👉 *If a director asks: "How do you prevent false positives — deals that aren't real deals?"*  
Say: "Every article goes through four independent checks before it's accepted. The first two are free, instant code-level checks. Only articles that pass both go to the AI for deeper analysis. The AI's full reasoning is recorded for every single decision, so you can always audit why something was accepted or rejected."

👉 *If a director asks: "What if the AI makes a mistake?"*  
Say: "The AI's confidence score is recorded for every deal. Anything with less than 80% confidence goes into a 'Review Queue' sheet in the report — specifically flagged for human analyst review. High-confidence deals go straight to the final sheets. We designed the system to never silently accept a doubtful deal."

---

## FLOWCHART 4: "Data Sources & Output Structure"
*(The left-right funnel showing inputs and outputs)*

### What this diagram shows in one sentence:
**"On the left is everything we read. In the middle is our engine. On the right is what we produce."**

---

### Left Side: The 84 Input Sources

Think of these as 84 newspapers and bulletins the system subscribes to — but instead of reading them manually, the software reads all 84 simultaneously every time it runs.

**Wire Services (BusinessWire, GlobeNewswire, PR Newswire, Reuters)**
These are the most important sources. When a company makes a major deal, they are legally and commercially required to issue a press release through one of these wire services. This is where the highest-quality, most confirmed deal announcements appear. Think of these as the "official announcement boards" of the corporate world.

**Energy News (Upstream Online, Oilprice.com, NGI, World Oil)**
Specialist trade publications that cover the energy sector in depth. These often have deal news before the mainstream financial press picks it up.

**Renewables (RenewablesNow, Recharge News, PV Tech)**
Specialist publications covering solar, wind, storage, and clean energy transactions. Critical for tracking the energy transition M&A landscape.

**Financial (Bloomberg Energy, S&P Global, Platts)**
High-authority financial intelligence sources. Platts and S&P Global Commodity Insights are the industry gold standard for energy pricing and deal intelligence.

**Government: SEC EDGAR (8-K, SC TO-T filings)**
This is unique and very powerful. In the USA, all public companies are legally required to file with the SEC (Securities and Exchange Commission) when a material transaction occurs. The system directly monitors these government filings — meaning it captures deals that may not even have appeared in the news yet. This is a significant competitive advantage.

---

### The How: RSS / Google News / Direct URL / Playwright Browser

These four methods are shown on the arrows in the middle. They describe how the system actually accesses each source:
- **RSS:** Like subscribing to a news feed — constant automatic updates
- **Google News:** Searching Google News for specific energy M&A terms
- **Direct URL:** Going directly to a specific news page
- **Playwright Browser:** For protected sites, using a stealth browser

---

### Right Side: The Excel Output — 9 Sheets

**Upstream** — Oil and gas exploration and production. Buying/selling of oil fields, drilling rights, E&P companies.

**Midstream** — The infrastructure that transports oil and gas. Pipelines, LNG terminals, gas processing plants, storage facilities.

**OFS (Oilfield Services)** — Companies that service the industry: drilling contractors, equipment providers, fracking companies.

**R&M (Refining & Marketing)** — Refineries, petrochemical plants, fuel retail stations, lubricants companies.

**P&U (Power & Utilities + Mining)** — Everything on the power and clean energy side: solar farms, wind farms, nuclear, hydro, battery storage, hydrogen projects, and mining companies (copper, lithium, gold — critical minerals for the energy transition).

**JV & Partnerships** — Deals that aren't full acquisitions yet. Joint ventures, MOUs (Memoranda of Understanding), and LOIs (Letters of Intent). These are "deals in progress" that might become full acquisitions.

**Review Queue** — Deals the AI accepted but wasn't fully certain about. These need a human to double-check before they're acted upon.

**Rejected by AI** — Full transparency log. Every article the AI reviewed and rejected, with the complete reasoning. If anyone ever questions why a particular deal wasn't reported, you can look it up here.

**Run Intelligence Dashboard** — The management overview page. Shows how many deals were found in each category, how many were rejected, AI processing statistics, and the AI-generated narrative summary of the day's market activity.

---

👉 *If a director asks: "Can we add a new news source?"*  
Say: "Absolutely. Each source is one entry in a master configuration file. Adding a new source requires no changes to any other part of the system — it simply feeds into the same pipeline automatically."

👉 *If a director asks: "Why do we need so many output sheets rather than one big list?"*  
Say: "Because our deal teams are structured by sector. The Upstream team doesn't want to wade through Renewables deals, and vice versa. The system automatically routes each deal to the correct sheet, so each team opens the report and their relevant deals are already pre-filtered for them."

---

## MASTER Q&A — Director Cross-Questions & Model Answers

| Question They Might Ask | What You Should Say |
|---|---|
| **"How accurate is this?"** | "The AI verification gate runs every article through 4 independent checks. High-confidence deals go straight to the report. Anything uncertain goes to the Review Queue for a human analyst to decide. We also keep a full log of every rejection with the AI's reasoning — so the system is completely auditable." |
| **"What if a website blocks you?"** | "The system automatically detects this and switches to a stealth browser that mimics real human behaviour. This happens in milliseconds, without human intervention." |
| **"How much does it cost to run?"** | "Near zero. The AI we use (Groq) is on a free tier. The news sources we access are either free RSS feeds or via Google News. The only costs are the server or PC that runs it." |
| **"Can competitors see we're monitoring their announcements?"** | "No. The system mimics standard web browsing behaviour and reads publicly available information — the same information any analyst would read manually. We access only what is publicly published." |
| **"How quickly does it run?"** | "25 to 40 minutes to scan 84 sources, run AI analysis on every article, and produce a finished Excel report. Manually, this would take one or two analysts a full working day." |
| **"What if we want to add more sources?"** | "Adding a source takes approximately 2 minutes — it's one entry in the configuration file. The rest of the system picks it up automatically." |
| **"Is this better than a Bloomberg Terminal?"** | "Bloomberg provides market data and some deal feeds. This system is targeted specifically at energy M&A, covers specialist trade press and government filings that Bloomberg doesn't index, and automatically categorises and structures every deal for immediate use. It's complementary, not competing." |
| **"Who maintains this?"** | "The system is self-maintaining in normal operation — it has a self-healing feedback loop that flags uncertain decisions for review. Maintenance is needed only when a news source changes its URL, or when we want to add new sources or categories." |
| **"Can it cover international deals?"** | "Yes. The system handles automatic currency conversion to USD for deal values in GBP, EUR, CAD, NOK, INR, and 15 other currencies. It also has built-in AI translation for non-English articles in Russian, Portuguese, and Spanish." |
| **"What happens when the AI is wrong?"** | "Every AI decision is logged with the full reasoning. Wrong acceptances go into the Review Queue. Wrong rejections — if they're important deals — can be flagged by analysts, and the system learns from those corrections for future runs through its self-learning memory." |
