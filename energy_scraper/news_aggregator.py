"""
news_aggregator.py — Enterprise multi-source M&A news aggregation layer.

Provides Cloudflare-immune article collection from:
  1. Native wire service RSS feeds (PR Newswire, GlobeNewswire, BusinessWire)
  2. Expanded Google News RSS M&A sweep (60+ targeted queries)
  3. SEC EDGAR FULL-TEXT search RSS

All articles are returned as standardised candidate dicts compatible with
the existing AsyncMAScraper pipeline (headline, url, date_hint).

CRITICAL: This module does NOT modify any existing code paths.
It is a pure additive data source.
"""

import random as _random

import asyncio
import logging
import urllib.parse
from datetime import datetime

import aiohttp
import feedparser

import dateutil.parser as dparser

try:
    from .config import RE_STRONG, RE_MEDIUM, RE_OTHER, is_energy_relevant
except ImportError:
    from config import RE_STRONG, RE_MEDIUM, RE_OTHER, is_energy_relevant

logger = logging.getLogger("energy_scraper.aggregator")

def _parse_date(date_str):
    if not date_str:
        return None
    try:
        dt = dparser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def _is_within_date_range(parsed_date, start_date, end_date):
    if not parsed_date:
        return False
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
        p = datetime.strptime(parsed_date, "%Y-%m-%d").date()
        return s <= p <= e
    except Exception:
        return False

def _headline_has_ma_signal(headline: str) -> bool:
    h = headline.lower()
    return bool(RE_STRONG.search(h) or RE_MEDIUM.search(h) or RE_OTHER.search(h))


# ─────────────────────────────────────────────────────────────
# Configuration — queries, feeds, and constants
# ─────────────────────────────────────────────────────────────

# Native RSS feeds from wire services (bypasses Cloudflare completely)
WIRE_RSS_FEEDS = {
    "GlobeNewswire — M&A": "https://www.globenewswire.com/RssFeed/subjectcode/14-Mergers%20and%20Acquisitions/feedTitle/GlobeNewswire%20-%20Mergers%20and%20Acquisitions",
    "GlobeNewswire — Energy": "https://www.globenewswire.com/RssFeed/subjectcode/15-Energy/industry/1000-Energy",
    "PR Newswire — Energy": "https://www.prnewswire.com/rss/energy-latest-news/energy-latest-news-list.rss",
    "BusinessWire — Energy": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVpTWg==",
    "BusinessWire — M&A": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEVtRXA==",
    "OilAndGas360 — M&A": "https://www.oilandgas360.com/category/mergers-acquisitions-divestitures/feed/",
    "RenewablesNow": "https://renewablesnow.com/rss/news",
    "Rigzone": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
    # FIX 4.2: Removed Bloomberg Markets RSS (produced oil-price/geopolitical noise)
    # FIX 4.2: Removed Yahoo Finance topstories RSS (produced savings rates, Cramer articles)
    # MarketWatch (WSJ parent company) energy RSS — no paywall
    "MarketWatch — Energy": "https://feeds.content.dowjones.io/public/rss/mw_energy",
}

# Google News RSS queries — each returns up to 100 results, all pre-indexed
# from major wire services. This is the key to 100% BusinessWire coverage.
#
# WIRE_SITE_QUERIES: These are injected with after:/before: date operators at
# runtime (inside _collect_google_news). Keep them separate so we can easily
# identify which queries should receive date filtering.
WIRE_SITE_QUERIES = [
    # ── BusinessWire ──
    "site:businesswire.com energy acquisition OR merger",
    "site:businesswire.com oil gas acquires OR buys",
    "site:businesswire.com renewable energy acquisition OR investment",
    # ── PR Newswire ──
    "site:prnewswire.com energy acquisition OR merger",
    "site:prnewswire.com oil gas acquires OR buys",
    "site:prnewswire.com renewable energy acquisition OR investment",
    # ── GlobeNewswire ──
    "site:globenewswire.com energy acquisition OR merger",
    "site:globenewswire.com oil gas acquires OR buys",
    "site:globenewswire.com mining acquisition OR merger",
    # ── Bloomberg (paywalled site — Google News indexes headlines+snippets) ──
    "site:bloomberg.com energy acquisition OR merger",
    "site:bloomberg.com energy acquires OR buys oil gas",
    # ── WSJ (paywalled — Google News indexes headlines+snippets) ──
    "site:wsj.com energy acquisition OR merger deal",
    "site:wsj.com oil gas acquires OR buys",
    # ── Reuters ──
    "site:reuters.com energy acquisition OR merger",
    "site:reuters.com oil gas acquisition OR deal",
]

GOOGLE_NEWS_MA_QUERIES = [
    # ── Tool-Specific: Broad energy M&A boolean queries (maximises coverage) ──
    '(energy OR oil OR gas OR solar OR wind OR mining) (acquisition OR merger OR buyout OR stake OR divest)',
    '(upstream OR midstream OR downstream OR refinery OR pipeline) (acquisition OR merger OR buyout OR divestment)',
    '(renewable OR "clean energy" OR geothermal OR nuclear OR hydrogen) (acquisition OR merger OR buyout OR deal)',
    '(utility OR "power plant" OR "energy storage" OR battery) (acquisition OR merger OR buyout OR joint venture)',
    '("shale" OR "permian" OR "offshore block" OR "working interest") (acquisition OR merger OR buyout OR divest)',
    '(mining OR lithium OR copper OR gold) (acquisition OR merger OR buyout OR mineral rights)',
    # ── High-Value Deals & Auctions ──
    '("rooftop solar" OR "solar project" OR "wind farm") (auction OR SECI OR tender win OR awarded)',
    # ── Wire site-specific broad queries ──
    'site:businesswire.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    'site:prnewswire.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    'site:globenewswire.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    # ── Major financial news broad queries ──
    'site:bloomberg.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    'site:wsj.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    'site:reuters.com (energy OR oil OR gas OR solar OR wind OR mining) (acquire OR merger OR buyout)',
    # ── Hard-Paywall Bypass (explicit snippet targets) ──
    'site:bloomberg.com (energy OR mining) ("oppose" OR "stake sale" OR "take private")',
    'site:wsj.com (energy OR mining) ("opposed" OR "stake sale" OR "takes private")',
    # ── Divestiture / Sale queries ──
    "energy company divests OR sells",
    "oil gas divestiture OR sale",
    "energy asset sale OR divestiture",
    # ── Joint venture queries ──
    "energy joint venture OR partnership",
    "oil gas joint venture",
    "renewable energy joint venture",
    # ── Regional energy M&A ──
    "Permian Basin acquisition OR merger",
    "North Sea energy deal OR acquisition",
    "Gulf of Mexico acquisition OR divestiture",
    "Africa energy acquisition OR deal",
    "India energy acquisition OR merger",
    "Europe energy acquisition OR deal",
    "Latin America energy acquisition OR merger",
    "Australia mining acquisition OR merger",
    "Canada energy acquisition OR merger",
    "Middle East energy acquisition OR investment",
    # ── Multi-lingual M&A queries ──
    "acquisition énergie fusion OR rachat",            # French
    "adquisición energía fusión OR compra",            # Spanish
    "Übernahme Energie Fusion OR Kauf",                # German
    "придбання енергія злиття OR покупка",             # Ukrainian
]

# SEC EDGAR full-text search for energy M&A filings
SEC_EDGAR_QUERIES = [
    "energy merger acquisition",
    "oil gas acquisition",
    "renewable energy merger",
]


def _build_google_news_rss_url(query: str) -> str:
    """Build a Google News RSS URL from a search query string."""
    encoded = urllib.parse.quote_plus(query)
    return (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )


def _build_sec_efts_url(query: str, start_date: str, end_date: str) -> str:
    """Build a SEC EDGAR FULL-TEXT search URL filtered by date range."""
    encoded = urllib.parse.quote_plus(query)
    return (
        f"https://efts.sec.gov/LATEST/search-index"
        f"?q={encoded}&dateRange=custom"
        f"&startdt={start_date}&enddt={end_date}"
        f"&forms=8-K,S-1,DEFM14A"
    )


# ─────────────────────────────────────────────────────────────
# AsyncNewsAggregator
# ─────────────────────────────────────────────────────────────

class AsyncNewsAggregator:
    """
    Collects M&A article candidates from multiple free sources.
    Returns a flat list of candidate dicts: {headline, url, date_hint, source}.
    All results are deduplicated by URL.
    """

    def __init__(self, start_date: str, end_date: str,
                 already_processed: set | None = None):
        self.start_date = start_date
        self.end_date = end_date
        self.already_processed = already_processed or set()
        self._seen_urls: set = set()
        self._candidates: list[dict] = []
        self._lock = asyncio.Lock()

    def _build_dated_query(self, base_query: str) -> str:
        """Append Google Search after:/before: date operators to a query."""
        return f"{base_query} after:{self.start_date} before:{self.end_date}"

    async def collect_all(self) -> list[dict]:
        """Run all aggregation sources in parallel and return deduplicated candidates."""
        logger.info("🔎 Aggregator: starting multi-source collection...")

        tasks = [
            self._collect_wire_rss(),
            self._collect_google_news(),
            self._collect_sec_edgar(),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            f"🔎 Aggregator: collected {len(self._candidates)} unique candidates "
            f"(excluded {len(self._seen_urls) - len(self._candidates)} duplicates)"
        )
        return self._candidates

    # ── Wire Service RSS ──

    async def _collect_wire_rss(self):
        """Parse native RSS feeds from wire services.
        
        A small random sleep between feeds prevents 429 rate-limiting from
        wire services that share infrastructure (e.g. Newswire, BusinessWire).
        """
        for source_name, feed_url in WIRE_RSS_FEEDS.items():
            # Jitter: space out RSS fetches to avoid tripping 429 rate limits
            await asyncio.sleep(_random.uniform(0.3, 1.0))
            try:
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                count = 0
                for entry in feed.entries:
                    url = entry.get("link", "")
                    title = entry.get("title", "")
                    date_hint = entry.get("published", entry.get("updated", None))
                    if self._add_candidate(title, url, date_hint, source_name):
                        count += 1
                logger.info(f"   ✅ {source_name}: {count} new articles")
            except Exception as exc:
                logger.warning(f"   ⚠ {source_name}: RSS failed — {exc}")

    # ── Google News RSS ──

    async def _collect_google_news(self):
        """Run expanded Google News RSS queries for energy M&A.
        
        Wire-site-specific queries (WIRE_SITE_QUERIES) get `after:/before:` date
        operators injected so Google only returns results in our date window.
        Broad queries (GOOGLE_NEWS_MA_QUERIES) are run without date filters to
        maximise coverage from aggregator/republishing sites.
        """
        sem = asyncio.Semaphore(3)  # Limit concurrent RSS fetches (reduced from 5 to avoid 429)

        async def _fetch_query(query: str, source_label: str):
            async with sem:
                rss_url = _build_google_news_rss_url(query)
                success = False
                try:
                    feed = await asyncio.to_thread(feedparser.parse, rss_url)
                    count = 0
                    if getattr(feed, "status", 200) != 429 and feed.entries:
                        for entry in feed.entries:
                            url = entry.get("link", "")
                            title = entry.get("title", "")
                            date_hint = entry.get("published", entry.get("updated", None))
                            if self._add_candidate(title, url, date_hint, source_label):
                                count += 1
                        if count > 0:
                            logger.debug(f"   Google News '{query[:50]}...' → {count} new")
                        success = True
                except Exception as exc:
                    pass

                # DuckDuckGo Zero-Cost API Failover
                if not success:
                    try:
                        from duckduckgo_search import DDGS
                        ddg_count = 0
                        with DDGS() as ddgs:
                            results = list(ddgs.news(query, max_results=10))
                        for res in results:
                            title = res.get("title", "")
                            url = res.get("url", "")
                            date_hint = res.get("date", "")
                            if self._add_candidate(title, url, date_hint, f"DDG Failover: {source_label}"):
                                ddg_count += 1
                        if ddg_count > 0:
                            logger.info(f"   ⚠ Google News Rate Limited. DDG Failover got {ddg_count} results for '{query[:30]}...'")
                    except Exception as ddg_exc:
                        logger.warning(f"   ⚠ Both Google and DDG Failed for '{query[:30]}...' — {ddg_exc}")

        # Date-filtered wire-site queries (most precise — return only in-range articles)
        wire_tasks = [
            _fetch_query(
                self._build_dated_query(q),
                f"Google News (dated): {q[:40]}"
            )
            for q in WIRE_SITE_QUERIES
        ]
        # Broad M&A sweep (no date filter — catches aggregators / republishers)
        broad_tasks = [
            _fetch_query(q, f"Google News: {q[:40]}")
            for q in GOOGLE_NEWS_MA_QUERIES
        ]

        all_tasks = wire_tasks + broad_tasks
        await asyncio.gather(*all_tasks, return_exceptions=True)
        total_queries = len(wire_tasks) + len(broad_tasks)
        logger.info(f"   ✅ Google News sweep: {len(wire_tasks)} dated wire queries + {len(broad_tasks)} broad queries = {total_queries} total")

    # ── SEC EDGAR ──

    async def _collect_sec_edgar(self):
        """Query SEC EDGAR FULL-TEXT search for energy M&A filings."""
        for query in SEC_EDGAR_QUERIES:
            url = _build_sec_efts_url(query, self.start_date, self.end_date)
            try:
                feed = await asyncio.to_thread(feedparser.parse, url)
                count = 0
                for entry in feed.entries:
                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    date_hint = entry.get("published", entry.get("updated", None))
                    if self._add_candidate(title, link, date_hint, "SEC EDGAR"):
                        count += 1
                logger.info(f"   ✅ SEC EDGAR '{query}': {count} filings")
            except Exception as exc:
                logger.warning(f"   ⚠ SEC EDGAR failed: {query} — {exc}")

    # ── Deduplication ──

    def _add_candidate(self, headline: str, url: str, date_hint, source: str) -> bool:
        """Thread-safe add with deduplication against self and already-processed URLs."""
        if not url or not headline or len(headline.strip()) < 10:
            return False

        if not _headline_has_ma_signal(headline):
            return False

        p_date = _parse_date(date_hint)
        if p_date and not _is_within_date_range(p_date, self.start_date, self.end_date):
            return False

        is_relevant = is_energy_relevant(headline, "")
        if not is_relevant:
            # For Google News, headline MUST be relevant.
            # For native RSS or SEC, we allow some ambiguity if the source name is a known energy source.
            if "google news" in source.lower():
                return False
            
            energy_source_keywords = ["energy", "oil", "gas", "renewables", "utility", "rigzone", "oilandgas360"]
            if not any(kw in source.lower() for kw in energy_source_keywords):
                return False

        # Normalise URL for dedup
        normalised = url.split("?")[0].rstrip("/").lower()

        if normalised in self._seen_urls:
            return False
        if normalised in self.already_processed:
            return False

        self._seen_urls.add(normalised)
        self._candidates.append({
            "headline": headline.strip(),
            "url": url,
            "date_hint": date_hint,
            "source": source,
        })
        return True
