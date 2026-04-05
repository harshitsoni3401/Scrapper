"""
agentic_agents.py — Self-Healing, Query Generation, and "Check My Work" agents.

Three additive AI agents running on free Groq API:

  1. SelfHealingAgent: When HTML parsing returns 0 articles despite a 200 OK response,
     sends a sample of the HTML to an LLM which identifies the correct CSS selectors.
     Results are cached in `selector_cache.json` so future runs re-use working selectors.

  2. QueryGenerationAgent: Dynamically generates additional Google News search queries
     by analyzing the current deal pipeline and surfacing trending topics or gaps.
     Supplements (does NOT replace) the hardcoded queries in news_aggregator.py.

  3. CheckMyWorkAgent: Post-processing QA pass that reviews the final deals list.
     Catches sheet mis-routing, non-M&A false positives that slipped through, and
     verifies entity extraction quality. Runs AFTER all deals are collected but
     BEFORE Excel export.

All agents are FREE — they use the existing Groq multi-key infrastructure.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path

logger = logging.getLogger("energy_scraper.agents")

_CACHE_DIR = Path(__file__).parent
_SELECTOR_CACHE = _CACHE_DIR / "selector_cache.json"


# ═══════════════════════════════════════════════════════════════
# AGENT 1: Self-Healing Selector Discovery
# ═══════════════════════════════════════════════════════════════

class SelfHealingAgent:
    """When a site returns HTML but the parser finds 0 articles,
    this agent sends a ~4000-char sample of the HTML to the LLM
    and asks it to identify the CSS selectors for article headlines.

    Results are cached persistently so the discovery only happens once
    per site, even across multiple runs.
    """

    def __init__(self, ai_extractor):
        """
        Args:
            ai_extractor: The existing AsyncAIExtractor instance (for Groq calls).
        """
        self.ai = ai_extractor
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self):
        try:
            if _SELECTOR_CACHE.exists():
                self._cache = json.loads(_SELECTOR_CACHE.read_text(encoding="utf-8"))
                logger.info(f"Self-Healing: Loaded {len(self._cache)} cached selectors")
        except Exception as e:
            logger.warning(f"Self-Healing: Could not load cache: {e}")
            self._cache = {}

    def _save_cache(self):
        try:
            _SELECTOR_CACHE.write_text(
                json.dumps(self._cache, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Self-Healing: Could not save cache: {e}")

    def get_cached_selectors(self, site_name: str) -> dict | None:
        """Return cached selectors for a site, or None if not cached."""
        entry = self._cache.get(site_name)
        if entry:
            logger.info(f"Self-Healing: Using cached selectors for {site_name}")
            return entry
        return None

    async def discover_selectors(self, site_name: str, html: str) -> dict | None:
        """Use AI to discover article headline selectors from raw HTML.

        Args:
            site_name: The site config name (e.g. 'Hart Energy')
            html: The raw HTML content (~4000 chars will be sampled)

        Returns:
            Dict with keys: article_container, headline_tag, link_tag, date_tag
            or None if discovery fails.
        """
        if not self.ai.enabled:
            return None

        # Check cache first
        cached = self.get_cached_selectors(site_name)
        if cached:
            return cached

        # Sample the HTML — take middle section (header/footer are usually noise)
        html_len = len(html)
        if html_len > 8000:
            start = html_len // 4
            sample = html[start:start + 4000]
        else:
            sample = html[:4000]

        prompt = f"""You are a web scraping expert. I have HTML from the news website '{site_name}'.
My generic article parser found 0 articles. I need you to identify the correct CSS selectors.

Here is a sample of the HTML (middle section of the page):

```html
{sample}
```

Analyze this HTML and identify:
1. The CSS selector for the container that wraps each article/news item
2. The CSS selector for the headline text within that container
3. The CSS selector for the article link (href) within that container
4. The CSS selector for the date/time element, if present

Reply ONLY with valid JSON in this exact format:
{{
  "article_container": "div.article-card",
  "headline_selector": "h2.title a",
  "link_selector": "h2.title a",
  "date_selector": "span.date",
  "confidence": 0.85,
  "notes": "Brief explanation of what you found"
}}

If you cannot identify the selectors with confidence, set confidence to 0.0.
"""
        try:
            messages = [
                {"role": "system", "content": "You are a web scraping CSS selector expert. Reply only in JSON."},
                {"role": "user", "content": prompt}
            ]
            result = await self.ai._generate(messages, use_json=True, json_mode="object")

            if result and isinstance(result, dict) and "article_container" in result:
                confidence = result.get("confidence", 0)
                if confidence >= 0.5:
                    self._cache[site_name] = result
                    self._save_cache()
                    logger.info(
                        f"Self-Healing: Discovered selectors for {site_name} "
                        f"(confidence={confidence}): container='{result['article_container']}'"
                    )
                    return result
                else:
                    logger.info(f"Self-Healing: Low confidence ({confidence}) for {site_name}, skipping cache")
                    return result
            else:
                logger.warning(f"Self-Healing: AI returned unexpected format for {site_name}")
                return None

        except Exception as e:
            logger.warning(f"Self-Healing: Discovery failed for {site_name}: {e}")
            return None

    def parse_with_discovered_selectors(self, soup, base_url: str, selectors: dict) -> list[dict]:
        """Parse articles using AI-discovered selectors.

        Args:
            soup: BeautifulSoup instance
            base_url: Base URL for resolving relative links
            selectors: Dict returned by discover_selectors()

        Returns:
            List of candidate dicts with headline, url, date_hint
        """
        from urllib.parse import urljoin

        container_sel = selectors.get("article_container", "")
        headline_sel = selectors.get("headline_selector", "")
        link_sel = selectors.get("link_selector", "")
        date_sel = selectors.get("date_selector", "")

        results = []
        seen = set()

        try:
            containers = soup.select(container_sel) if container_sel else []
        except Exception:
            containers = []

        if not containers:
            logger.debug(f"Self-Healing: Container selector '{container_sel}' matched 0 elements")
            return results

        for container in containers:
            # Extract headline
            headline = ""
            try:
                h_el = container.select_one(headline_sel) if headline_sel else None
                if h_el:
                    headline = h_el.get_text(strip=True)
            except Exception:
                pass

            if not headline:
                # Fallback: try any heading tag
                h_tag = container.find(["h1", "h2", "h3", "h4", "h5"])
                if h_tag:
                    headline = h_tag.get_text(strip=True)

            # Extract link
            url = None
            try:
                link_el = container.select_one(link_sel) if link_sel else None
                if link_el and link_el.get("href"):
                    url = urljoin(base_url, link_el["href"])
            except Exception:
                pass

            if not url:
                # Fallback: first <a> with href
                a_tag = container.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    if not href.startswith(("javascript", "#", "mailto")):
                        url = urljoin(base_url, href)

            # Extract date
            date_hint = None
            try:
                date_el = container.select_one(date_sel) if date_sel else None
                if date_el:
                    date_hint = date_el.get("datetime", date_el.get_text(strip=True))
            except Exception:
                pass

            if not date_hint:
                time_tag = container.find("time")
                if time_tag:
                    date_hint = time_tag.get("datetime", time_tag.get_text(strip=True))

            if url and url not in seen and headline and len(headline) >= 15:
                seen.add(url)
                results.append({
                    "headline": headline,
                    "url": url,
                    "date_hint": date_hint,
                })

        logger.info(f"Self-Healing: Parsed {len(results)} articles using discovered selectors")
        return results


# ═══════════════════════════════════════════════════════════════
# AGENT 2: Dynamic Query Generation
# ═══════════════════════════════════════════════════════════════

class QueryGenerationAgent:
    """Generates supplementary Google News search queries based on:
    1. Current date range
    2. Recently seen deals (to find related transactions)
    3. Known energy sector gaps (areas we have 0 coverage)

    These queries are additive — they supplement the hardcoded queries
    in news_aggregator.py, never replace them.
    """

    def __init__(self, ai_extractor):
        self.ai = ai_extractor

    async def generate_supplementary_queries(
        self, 
        start_date: str, 
        end_date: str,
        existing_deals: list[dict] = None,
        existing_queries: list[str] = None,
    ) -> list[str]:
        """Generate 5-10 additional targeted search queries.

        Args:
            start_date: Date range start (YYYY-MM-DD)
            end_date: Date range end (YYYY-MM-DD)
            existing_deals: Deals already found (for gap analysis)
            existing_queries: Hardcoded queries (to avoid duplication)

        Returns:
            List of new Google News search query strings.
        """
        if not self.ai.enabled:
            return []

        # Build context about what we already have
        deal_summary = ""
        if existing_deals:
            sectors_covered = set()
            companies = set()
            for d in existing_deals[:20]:  # Limit to 20 for token efficiency
                sectors_covered.add(d.get("Industry", ""))
                companies.add(d.get("Buyer", ""))
                companies.add(d.get("Seller", ""))
            sectors_covered.discard("")
            companies.discard("")
            companies.discard("Unknown")
            deal_summary = (
                f"Sectors already covered: {', '.join(list(sectors_covered)[:10])}\n"
                f"Companies already seen: {', '.join(list(companies)[:15])}\n"
                f"Total deals found so far: {len(existing_deals)}"
            )

        prompt = f"""You are ARIA (Autonomous Research Intelligence for Acquisitions), an expert M&A analyst.
Your task is to perform a GAP ANALYSIS on our current run session and generate 5-10 supplemental Google News search queries to ensure 100% market coverage.

DATE RANGE: {start_date} to {end_date}

CURRENT PIPELINE STATUS:
{deal_summary if deal_summary else "No deals found yet this run."}

OUR STANDARD MONITORING COVERS:
- Major oil & gas acquisitions (Permian Basin, North Sea, Gulf of Mexico)
- Renewable energy M&A (solar, wind, battery storage)
- Mining acquisitions (lithium, copper, gold)

IDENTIFY THE GAPS:
Based on the status above, what is MISSING? 
Focus your 5-10 new queries on:
1. Missing Sectors: If we found no Hydrogen, Nuclear, Geothermal, or CCUS deals, target those specifically.
2. Missing Geographies: If we are thin on Africa, Southeast Asia, or Latin America, target energy M&A in those regions.
3. Emerging Trends: Target specific acquirers seen today to find related sub-deals.
4. Private Equity: Target energy fund acquisitions in under-represented sectors.

Reply ONLY with a JSON array of query strings. Each query must:
- Use proper Google search operators (e.g., 'site:reuters.com', 'intitle:acquisition').
- Be highly specific to avoid noise.

Format: ["query1", "query2", ...]"""

        try:
            messages = [
                {"role": "system", "content": "You are ARIA, performing an M&A gap analysis. Reply only with a JSON array of strings."},
                {"role": "user", "content": prompt}
            ]
            result = await self.ai._generate(messages, use_json=True, json_mode="any")

            if result and isinstance(result, list):
                queries = [q for q in result if isinstance(q, str) and len(q) > 10]
                logger.info(f"ARIA QueryGen: Identified gaps and generated {len(queries)} supplementary queries")
                return queries[:10]  # Cap at 10
            elif result and isinstance(result, dict):
                # Sometimes LLM wraps in {"queries": [...]}
                for key in ("queries", "search_queries", "results"):
                    if key in result and isinstance(result[key], list):
                        queries = [q for q in result[key] if isinstance(q, str) and len(q) > 10]
                        logger.info(f"QueryGen: Generated {len(queries)} supplementary queries")
                        return queries[:10]

            logger.warning(f"QueryGen: Unexpected response format: {str(result)[:200]}")
            return []

        except Exception as e:
            logger.warning(f"QueryGen: Failed to generate queries: {e}")
            return []


# ═══════════════════════════════════════════════════════════════
# AGENT 3: "Check My Work" Post-Processing QA
# ═══════════════════════════════════════════════════════════════

class CheckMyWorkAgent:
    """Post-processing QA agent that reviews the final deals list before Excel export.

    Checks for:
    1. Sheet mis-routing (e.g., mining deal in OFS, utility in Upstream)
    2. Non-M&A false positives that slipped through all filters
    3. Entity extraction quality (buyer/seller/asset sanity)
    4. Duplicate deals with different wording
    5. Obvious non-energy content

    Runs in batch mode: sends 5-10 deals at a time to the LLM for review.
    Modifies deals in-place (fixes Sheet, flags issues).
    """

    def __init__(self, ai_extractor):
        self.ai = ai_extractor
        self._stats = {"reviewed": 0, "fixed": 0, "flagged": 0}

    async def review_all_deals(self, deals: list[dict], rejected: list[dict] = None) -> dict:
        """Review all deals and apply corrections.

        Args:
            deals: The final deals list (modified in-place)
            rejected: Rejected deals (checked for false negatives)

        Returns:
            Summary dict with stats
        """
        if not self.ai.enabled or not deals:
            return {"status": "skipped", "reason": "AI disabled or no deals"}

        logger.info(f"CheckMyWork: Reviewing {len(deals)} deals...")
        print(f"\n  🔍 Check-My-Work Agent: Reviewing {len(deals)} deals for quality...")

        # Process in batches of 8
        batch_size = 8
        for i in range(0, len(deals), batch_size):
            batch = deals[i:i + batch_size]
            corrections = await self._review_batch(batch, i)
            if corrections:
                self._apply_corrections(batch, corrections, i)

        # Check for obvious false negatives in rejected list
        rescued = 0
        if rejected:
            rescued = await self._rescue_false_negatives(deals, rejected)

        summary = {
            "reviewed": self._stats["reviewed"],
            "fixed": self._stats["fixed"],
            "flagged": self._stats["flagged"],
            "rescued_from_rejected": rescued,
        }

        print(f"  ✅ Check-My-Work: Reviewed {summary['reviewed']} deals, "
              f"fixed {summary['fixed']}, flagged {summary['flagged']}, "
              f"rescued {rescued} from rejected pile")
        logger.info(f"CheckMyWork: {summary}")
        return summary

    async def _review_batch(self, batch: list[dict], offset: int) -> list[dict] | None:
        """Send a batch of deals to AI for quality review.

        Returns a list of correction dicts, one per deal in the batch.
        """
        deal_summaries = []
        for idx, d in enumerate(batch):
            deal_summaries.append(
                f"Deal #{offset + idx + 1}:\n"
                f"  Headline: {d.get('Headline', '')[:100]}\n"
                f"  Buyer: {d.get('Buyer', 'Unknown')}\n"
                f"  Seller: {d.get('Seller', 'Unknown')}\n"
                f"  Asset: {d.get('Asset', 'Unknown')}\n"
                f"  Industry: {d.get('Industry', '')}\n"
                f"  Sheet: {d.get('Sheet', 'P&U')}\n"
                f"  Confidence: {d.get('Confidence', 0):.2f}\n"
                f"  Deal Type: {d.get('Deal Type', 'M&A')}"
            )

        deals_text = "\n\n".join(deal_summaries)

        prompt = f"""You are an energy M&A quality control analyst. Review these deals for correctness.

AVAILABLE SHEETS AND THEIR CORRECT USAGE:
- Upstream: Oil & gas E&P, exploration, production, drilling assets, shale, deepwater
- Midstream: Pipelines, gathering systems, processing plants, LNG terminals, storage
- OFS: Oilfield services, drilling rigs, equipment, service companies
- R&M: Refining, downstream, fuel distribution, petrochemicals
- P&U: Power plants, utilities, grid, renewable energy, solar, wind, battery storage, geothermal, nuclear, mining, metals, carbon capture, hydrogen, EV charging
- JV & Partnerships: Joint ventures, strategic alliances, MOUs
- Reports: Market reports, industry analysis (NOT actual M&A deals)

IMPORTANT: Mining & metals deals (gold, copper, lithium, iron ore, etc.) go in the P&U sheet.

For each deal, check:
1. Is the Sheet assignment correct based on the headline/industry?
2. Is this actually an M&A deal (not market commentary, insider trading, or general news)?
3. Are Buyer and Seller plausible (not generic terms or company descriptions)?

{deals_text}

Reply ONLY with a JSON array. One object per deal, in the same order:
[
  {{
    "deal_index": 0,
    "sheet_correct": true,
    "correct_sheet": "P&U",
    "is_real_deal": true,
    "issues": [],
    "action": "none"
  }},
  {{
    "deal_index": 1,
    "sheet_correct": false,
    "correct_sheet": "OFS",
    "is_real_deal": true,
    "issues": ["Sheet should be OFS — oilfield services company"],
    "action": "fix_sheet"
  }}
]

Valid actions: "none", "fix_sheet", "flag_review", "flag_not_deal"
"""
        try:
            messages = [
                {"role": "system", "content": "You are an energy M&A quality control analyst. Reply only with a JSON array."},
                {"role": "user", "content": prompt}
            ]
            result = await self.ai._generate(messages, use_json=True, json_mode="any")

            if result and isinstance(result, list):
                self._stats["reviewed"] += len(batch)
                return result
            elif result and isinstance(result, dict):
                # Sometimes wrapped in {"corrections": [...]}
                for key in ("corrections", "deals", "results", "reviews"):
                    if key in result and isinstance(result[key], list):
                        self._stats["reviewed"] += len(batch)
                        return result[key]

            logger.warning(f"CheckMyWork: Unexpected batch response")
            return None

        except Exception as e:
            logger.warning(f"CheckMyWork: Batch review failed: {e}")
            return None

    def _apply_corrections(self, batch: list[dict], corrections: list[dict], offset: int):
        """Apply corrections from AI review to the actual deal records."""
        for correction in corrections:
            try:
                idx = correction.get("deal_index", -1)
                if 0 <= idx < len(batch):
                    deal = batch[idx]
                    action = correction.get("action", "none")

                    if action == "fix_sheet":
                        old_sheet = deal.get("Sheet", "?")
                        new_sheet = correction.get("correct_sheet", old_sheet)
                        if new_sheet and new_sheet != old_sheet:
                            deal["Sheet"] = new_sheet
                            self._stats["fixed"] += 1
                            issues = correction.get("issues", [])
                            reason = issues[0] if issues else "Sheet corrected by QA agent"
                            logger.info(
                                f"CheckMyWork: Fixed deal #{offset + idx + 1} "
                                f"sheet {old_sheet} → {new_sheet}: "
                                f"{deal.get('Headline', '')[:50]} ({reason})"
                            )

                    elif action == "flag_review":
                        deal["Confidence"] = min(deal.get("Confidence", 0.5), 0.45)
                        self._stats["flagged"] += 1
                        logger.info(
                            f"CheckMyWork: Flagged deal #{offset + idx + 1} for review: "
                            f"{deal.get('Headline', '')[:50]}"
                        )

                    elif action == "flag_not_deal":
                        deal["Confidence"] = 0.10  # Will go to review queue
                        deal["Sheet"] = "P&U"  # Ensure it doesn't land in main sheets
                        self._stats["flagged"] += 1
                        logger.info(
                            f"CheckMyWork: Flagged deal #{offset + idx + 1} as NOT a deal: "
                            f"{deal.get('Headline', '')[:50]}"
                        )

            except Exception as e:
                logger.warning(f"CheckMyWork: Error applying correction: {e}")

    async def _rescue_false_negatives(self, deals: list[dict], rejected: list[dict]) -> int:
        """Check if any rejected deals are actually valid energy M&A that were wrongly rejected.

        Only checks high-confidence rejections for keywords that suggest real deals.
        """
        if not rejected:
            return 0

        rescue_candidates = []
        strong_deal_patterns = re.compile(
            r"\b(acqui|merger|takeover|buyout|divest|spin.?off|joint venture)\b",
            re.IGNORECASE
        )
        energy_patterns = re.compile(
            r"\b(oil|gas|energy|solar|wind|power|utility|mining|pipeline|lng|nuclear|battery)\b",
            re.IGNORECASE
        )

        for d in rejected:
            headline = d.get("Headline", "")
            # Only rescue deals that have BOTH strong M&A and energy signals
            if strong_deal_patterns.search(headline) and energy_patterns.search(headline):
                conf = d.get("Confidence", 0)
                if conf >= 0.30:  # Must have had some initial confidence
                    rescue_candidates.append(d)

        if not rescue_candidates:
            return 0

        # Limit to top 5 candidates
        rescue_candidates = rescue_candidates[:5]

        prompt_deals = "\n".join([
            f"- {d.get('Headline', '')[:100]} (Rejection: {d.get('Rejection Reason', 'unknown')[:60]})"
            for d in rescue_candidates
        ])

        prompt = f"""These deals were rejected by the AI but contain strong energy M&A signals.
Should any of them be rescued (they are real energy M&A deals that were wrongly rejected)?

{prompt_deals}

Reply with a JSON array of indices (0-based) to rescue. Example: [0, 2]
If none should be rescued, reply: []
"""
        try:
            messages = [
                {"role": "system", "content": "You are an energy M&A expert. Reply only with a JSON array of integers."},
                {"role": "user", "content": prompt}
            ]
            result = await self.ai._generate(messages, use_json=True, json_mode="any")

            rescued = 0
            if result and isinstance(result, list):
                for idx in result:
                    if isinstance(idx, int) and 0 <= idx < len(rescue_candidates):
                        deal = rescue_candidates[idx]
                        deal["Confidence"] = 0.55  # Moderate confidence
                        deal["Sheet"] = deal.get("Sheet", "P&U")
                        deal.pop("Rejection Reason", None)
                        deals.append(deal)
                        rescued += 1
                        logger.info(
                            f"CheckMyWork: RESCUED deal from rejected: "
                            f"{deal.get('Headline', '')[:60]}"
                        )
            elif result and isinstance(result, dict):
                for key in ("indices", "rescue", "results"):
                    if key in result and isinstance(result[key], list):
                        for idx in result[key]:
                            if isinstance(idx, int) and 0 <= idx < len(rescue_candidates):
                                deal = rescue_candidates[idx]
                                deal["Confidence"] = 0.55
                                deal["Sheet"] = deal.get("Sheet", "P&U")
                                deal.pop("Rejection Reason", None)
                                deals.append(deal)
                                rescued += 1

            return rescued

        except Exception as e:
            logger.warning(f"CheckMyWork: Rescue check failed: {e}")
            return 0

    async def generate_run_summary(self, deals: list[dict]) -> str:
        """Generating a 5-sentence executive narrative of the current run."""
        if not self.ai.enabled or not deals:
            return "No deals discovered in this run session."

        deal_list = "\n".join([
            f"- {d.get('Headline', '')[:90]} (Buyer: {d.get('Buyer', 'N/A')}, Value: {d.get('Value', 'Undisclosed')})"
            for d in deals[:30]
        ])

        prompt = f"""You are ARIA, the lead M&A intelligence engine. Provide a 5-sentence executive summary of today's energy M&A run based on these results:

DEALS FOUND:
{deal_list}

Your summary MUST include:
1. The most active acquirer(s) seen today.
2. The largest or most significant deal by value or strategic impact.
3. Notable geographic trends (e.g., 'Heavy activity in the Permian Basin' or 'Southeast Asia solar consolidation').
4. A comment on the overall market sentiment (e.g., 'Renewable targets outpaced traditional E&P').
5. One 'Sector to Watch' based on today's pipeline gaps or emerging themes.

Reply with ONLY the 5-sentence paragraph. No conversational intro/outro."""

        try:
            messages = [
                {"role": "system", "content": "You are ARIA. Provide a 5-sentence executive narrative only."},
                {"role": "user", "content": prompt}
            ]
            # Use _generate directly for raw text output
            result = await self.ai._generate(messages, use_json=False)
            if result and isinstance(result, str):
                summary = result.strip()
                logger.info("ARIA: Generated final executive narrative.")
                return summary
            return "Run summary generation failed."
        except Exception as e:
            logger.warning(f"CheckMyWork: Summary generation failed: {e}")
            return "Error generating run summary."
