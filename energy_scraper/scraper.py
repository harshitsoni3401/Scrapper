"""
scraper.py — Enterprise Async M&A Scraper engine.

Features:
  • Pure Async execution via asyncio and aiohttp
  • Thread-safe metric updates and logging via asyncio.Lock
  • Shared AsyncPlaywright browser instantiation for JS sites
  • Gemini Google-Search Grounding Fallback
"""

import re
import logging
import traceback
import asyncio
import os
import sys
import time
import json
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    from .config import TARGET_SITES, RE_STRONG, RE_MEDIUM, RE_OTHER, is_energy_relevant, classify_deal_sheet, transaction_signal_profile
    from .fetcher import AsyncSmartFetcher
    from .browser import AsyncBrowserManager
    from .extractor import DealExtractor
    from .excel_writer import ExcelReportWriter
    from .google_sheets import GoogleSheetsManager
    from .news_aggregator import AsyncNewsAggregator
    from .db_manager import DealDatabase
    from .agentic_agents import SelfHealingAgent, QueryGenerationAgent, CheckMyWorkAgent
    from .project_paths import FEEDBACK_DIR, GOOGLE_CREDENTIALS_PATH, SEEN_CACHE_PATH, SOURCE_HEALTH_PATH, ensure_runtime_dirs
except ImportError:
    from config import TARGET_SITES, RE_STRONG, RE_MEDIUM, RE_OTHER, is_energy_relevant, classify_deal_sheet, transaction_signal_profile
    from fetcher import AsyncSmartFetcher
    from browser import AsyncBrowserManager
    from extractor import DealExtractor
    from excel_writer import ExcelReportWriter
    from google_sheets import GoogleSheetsManager
    from news_aggregator import AsyncNewsAggregator
    from db_manager import DealDatabase
    from agentic_agents import SelfHealingAgent, QueryGenerationAgent, CheckMyWorkAgent
    from project_paths import FEEDBACK_DIR, GOOGLE_CREDENTIALS_PATH, SEEN_CACHE_PATH, SOURCE_HEALTH_PATH, ensure_runtime_dirs

logger = logging.getLogger("energy_scraper.scraper")


def _configure_console_output():
    """Prefer UTF-8 console output so direct script entry points do not crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────
# Headline validation
# ─────────────────────────────────────────────────────────────

_NAV_JUNK = {
    "home", "about", "contact", "login", "register", "sign in", "sign up",
    "subscribe", "menu", "search", "privacy policy", "terms", "cookies",
    "advertise", "careers", "faq", "frequently asked questions",
    "recruitment area", "corporate social responsibility",
    "airlines & aviation", "tendersnews", "inverters & bos",
    "construction and materials news", "industry insights & opinions",
    "asia & australia", "mexico", "hydraulic fracturing", "solar",
    "microgrid", "the latest lng news", "the wall street journal",
    "home | fom perth 2026", "see all", "read more", "view all",
    "back to top", "share this", "print this", "email this",
    "stop the presses", "investment banking and brokerage services news",
    "overview", "products", "services", "solutions", "resources",
    "events", "webinars", "podcasts", "videos", "reports",
    "press releases", "media contacts", "investor relations",
    "sustainability", "governance", "leadership", "our team",
    "partners", "clients", "portfolio", "blog",
}

# FIX 1.4: Block Reuters SPAC stub pages and Bloomberg ticker placeholders
# e.g. "About Miluna Acquisition Corp (MMTXU.OQ) - Reuters"
# e.g. "486630.KR | KB No.30 Special Purpose Acquisition Co. Quarterly Balance Sheet"
_SPAC_STUB_RE = re.compile(
    r"^about\s+[\w\s]+\s+(acquisition|spac|corp|inc)[\s.()]*"
    r"|^\d{4,6}\.\w{2}\s*\|"
    r"|investment banking scorecard"
    r"|wsj pro private equity",
    re.IGNORECASE,
)


def _is_valid_headline(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if len(t) < 15 or " " not in t:
        return False
    if t.lower() in _NAV_JUNK:
        return False
    if _SPAC_STUB_RE.match(t):  # FIX 1.4: Block SPAC stub headlines
        return False
    if t.startswith("#") or t.startswith("{"):
        return False
    if len(t) < 25 and t.isupper():
        return False
    return True


def _headline_has_ma_signal(headline: str) -> bool:
    h = (headline or "").lower()
    profile = transaction_signal_profile(h, "")
    if profile["structural"]:
        return True
    if profile["strong_keyword"] and not profile["weak_only"] and not profile["negative_context"]:
        return True
    if profile["medium_keyword"] and not profile["negative_context"]:
        return True
    return bool(RE_OTHER.search(h) and not profile["negative_context"])


def _parse_relative_date(hint: str) -> str | None:
    """Convert Newsfilter relative dates ('2D ago', '1h ago', '10m ago') to ISO dates."""
    if not hint:
        return None
    import re as _re
    from datetime import timedelta
    m = _re.search(r'(\d+)\s*([mhDdWw])', hint)
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2).lower()
    now = datetime.now()
    delta_map = {'m': timedelta(minutes=val), 'h': timedelta(hours=val),
                 'd': timedelta(days=val), 'w': timedelta(weeks=val)}
    delta = delta_map.get(unit)
    if delta:
        return (now - delta).strftime("%Y-%m-%d")
    return None


def _clean_newsfilter_headline(headline: str) -> str:
    """Strip '1D ago', '48m ago' time prefixes and trailing source names from Newsfilter headlines."""
    import re as _re
    # Remove leading relative time like '1D ago', '48m ago', '2h ago'
    headline = _re.sub(r'^\d+[mhDdWw]\s*ago\s*', '', headline).strip()
    # Remove trailing source names: 'Reuters', 'BusinessWire', etc.
    headline = _re.sub(r'(Reuters|BusinessWire|PR Newswire|GlobeNewswire|Bloomberg|Associated Press)\s*$', '', headline).strip()
    return headline


def _normalise_url(href: str, base_url: str):
    if not href or href.startswith("javascript") or href.startswith("#") or href.startswith("mailto"):
        return None
    return urljoin(base_url, href)


class SeenCache:
    """Persistent URL/title cache to avoid reprocessing across runs."""
    def __init__(self, path: Path, ttl_days: int = 30):
        self.path = Path(path)
        self.ttl_seconds = ttl_days * 24 * 3600
        self.urls: dict[str, float] = {}
        self.titles: dict[str, float] = {}
        self._load()

    def _now(self) -> float:
        return time.time()

    def _is_fresh(self, ts: float) -> bool:
        return (self._now() - ts) <= self.ttl_seconds

    def _hash(self, value: str) -> str:
        clean = re.sub(r"\s+", " ", value.strip().lower())
        return hashlib.md5(clean.encode("utf-8")).hexdigest()

    def _norm_url(self, url: str) -> str:
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", "")).lower().rstrip("/")
        except Exception:
            return (url or "").lower().strip()

    def _load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.urls = {k: v for k, v in data.get("urls", {}).items() if self._is_fresh(v)}
                self.titles = {k: v for k, v in data.get("titles", {}).items() if self._is_fresh(v)}
        except Exception:
            self.urls = {}
            self.titles = {}

    def is_seen(self, url: str, title: str) -> bool:
        url_norm = self._norm_url(url) if url else ""
        title_norm = (title or "").strip()
        if url_norm:
            key = self._hash(url_norm)
            if key in self.urls and self._is_fresh(self.urls[key]):
                return True
        if title_norm and len(title_norm) >= 12:
            key = self._hash(title_norm)
            if key in self.titles and self._is_fresh(self.titles[key]):
                return True
        return False

    def mark(self, url: str, title: str) -> None:
        now = self._now()
        if url:
            self.urls[self._hash(self._norm_url(url))] = now
        if title and len(title.strip()) >= 12:
            self.titles[self._hash(title)] = now

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "urls": self.urls,
                "titles": self.titles,
                "updated": datetime.now().isoformat(),
            }
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass


class SourceHealthTracker:
    """Tracks per-source health and deprioritizes persistently weak sources."""
    def __init__(self, path: Path, deprioritize_days: int = 7):
        self.path = Path(path)
        self.deprioritize_days = deprioritize_days
        self.data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.data = {}

    def _score_for_run(self, access_mode: str, status: str, articles_found: int) -> float:
        if access_mode in ("Blocked", "Failed"):
            return 0.0
        if access_mode == "Headline-Only":
            return 0.4
        if status.startswith("⚠") or "Partial" in status:
            return 0.3
        if articles_found <= 0:
            return 0.2
        return 1.0

    def update(self, site_name: str, access_mode: str, status: str, articles_found: int) -> None:
        now = datetime.now().isoformat()
        record = self.data.get(site_name, {
            "score": 1.0,
            "runs": 0,
            "last_run": None,
            "last_fail": None,
            "last_status": "",
            "last_access": "",
        })
        current = self._score_for_run(access_mode, status, articles_found)
        prev = float(record.get("score", 1.0))
        record["score"] = round((prev * 0.7) + (current * 0.3), 3)
        record["runs"] = int(record.get("runs", 0)) + 1
        record["last_run"] = now
        record["last_status"] = status
        record["last_access"] = access_mode
        if access_mode in ("Blocked", "Failed") or articles_found == 0:
            record["last_fail"] = now
        self.data[site_name] = record

    def score(self, site_name: str) -> float:
        try:
            return float(self.data.get(site_name, {}).get("score", 1.0))
        except Exception:
            return 1.0

    def deprioritize(self, site_name: str) -> bool:
        record = self.data.get(site_name, {})
        score = float(record.get("score", 1.0) or 1.0)
        last_fail = record.get("last_fail")
        if score >= 0.35 or not last_fail:
            return False
        try:
            fail_dt = datetime.fromisoformat(last_fail)
            days = (datetime.now() - fail_dt).days
            return days <= self.deprioritize_days
        except Exception:
            return False

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Article-list parsers
# ─────────────────────────────────────────────────────────────

def _generic_article_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()

    for art in soup.find_all("article"):
        a_tag = art.find("a", href=True)
        h_tag = art.find(["h1", "h2", "h3", "h4"])
        headline = h_tag.get_text(strip=True) if h_tag else (a_tag.get_text(strip=True) if a_tag else "")
        url = _normalise_url(a_tag["href"], base_url) if a_tag else None
        date_hint = None
        time_tag = art.find("time")
        if time_tag:
            date_hint = time_tag.get("datetime", time_tag.get_text(strip=True))
        if not date_hint:
            ds = art.find("span", class_=re.compile(r"date|time|pubdate", re.I))
            if ds:
                date_hint = ds.get_text(strip=True)
        if url and url not in seen and _is_valid_headline(headline):
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    pattern = re.compile(r"article|post|news|story|item|entry|card|result|release|listing|mb-4|pr-list|wire-release|feed-item", re.I)
    for div in soup.find_all(["div", "section", "li"], class_=pattern):
        a_tag = div.find("a", href=True)
        h_tag = div.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if h_tag:
            headline = h_tag.get_text(strip=True)
        elif a_tag:
            headline = a_tag.get_text(strip=True)
        else:
            # Fallback for divs that represent the row themselves
            headline = div.get_text(strip=True)[:100]

        url = _normalise_url(a_tag["href"], base_url) if a_tag else None
        date_hint = None
        time_tag = div.find("time")
        if time_tag:
            date_hint = time_tag.get("datetime", time_tag.get_text(strip=True))
        if not date_hint:
            ds = div.find("span", class_=re.compile(r"date|time|pubdate|posted", re.I))
            if ds:
                date_hint = ds.get_text(strip=True)
        if url and url not in seen and _is_valid_headline(headline):
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    for li in soup.find_all("li"):
        a_tag = li.find("a", href=True)
        if not a_tag:
            continue
        headline = a_tag.get_text(strip=True)
        url = _normalise_url(a_tag["href"], base_url)
        if url and url not in seen and _is_valid_headline(headline):
            seen.add(url)
            date_hint = None
            time_tag = li.find("time")
            if time_tag:
                date_hint = time_tag.get("datetime", time_tag.get_text(strip=True))
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    url_pat = re.compile(r"/(20\d{2}|article|news|story|press.release|press-release)/", re.I)
    for a_tag in soup.find_all("a", href=True):
        url = _normalise_url(a_tag["href"], base_url)
        if not url or url in seen:
            continue
        if not url_pat.search(url):
            continue
        headline = a_tag.get_text(strip=True)
        if _is_valid_headline(headline):
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": None})

    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(strip=True)
        if not _is_valid_headline(text):
            continue
        a_tag = heading.find("a", href=True)
        if not a_tag:
            parent = heading.parent
            if parent:
                a_tag = parent.find("a", href=True)
        if a_tag:
            url = _normalise_url(a_tag["href"], base_url)
            if url and url not in seen:
                seen.add(url)
                results.append({"headline": text, "url": url, "date_hint": None})

    return results

def _energy_pedia_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()

    # Main news feed
    for a_tag in soup.select("a[href*='/news/']"):
        url = _normalise_url(a_tag["href"], base_url)
        if not url or url in seen:
            continue
        headline = a_tag.get_text(strip=True)
        if _is_valid_headline(headline):
            seen.add(url)
            # Date is usually the previous text node
            date_hint = None
            parent = a_tag.parent
            if parent:
                text_content = parent.get_text(strip=True)
                import re as _re
                match = _re.search(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{2})', text_content)
                if match:
                    date_hint = match.group(1)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    # Sidebar: Publicly Available Deals (Very High Value)
    for a_tag in soup.select("a[href*='energy-pediaopportunities.com']"):
        url = _normalise_url(a_tag["href"], base_url)
        if not url or url in seen:
            continue
        headline = a_tag.get_text(strip=True)
        if _is_valid_headline(headline):
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": None})

    return results


def _nhst_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()
    nhst_url_pat = re.compile(r"/\d+-\d+-\d+$")

    for a_tag in soup.find_all("a", href=True):
        url = _normalise_url(a_tag["href"], base_url)
        if not url or url in seen:
            continue
        if not nhst_url_pat.search(url):
            continue
        headline = a_tag.get_text(strip=True)
        headline = re.sub(r"\d{2}\.\d{2}\.\d{4}$", "", headline).strip()
        categories = ["Exploration", "Production", "Field Development", "LNG",
                       "Energy Security", "Rigs and Vessels", "Pipelines",
                       "Renewable Energy", "M&A", "Finance",
                       "Wind", "Solar", "Energy Storage", "Policy",
                       "Vessels", "Technology", "Auctions", "Suppliers",
                       "Floating Wind", "Hydrogen", "Analysis",
                       "Accidents and Casualties"]
        for cat in categories:
            if headline.endswith(cat):
                headline = headline[:-len(cat)].strip()

        date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", a_tag.get_text())
        date_hint = date_match.group(1) if date_match else None

        if _is_valid_headline(headline):
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    for h3 in soup.find_all("h3"):
        text = h3.get_text(strip=True)
        a_tag = h3.find("a", href=True)
        if a_tag:
            url = _normalise_url(a_tag["href"], base_url)
            if url and url not in seen and _is_valid_headline(text):
                seen.add(url)
                results.append({"headline": text, "url": url, "date_hint": None})

    return results


def _neftegaz_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()

    # The actual Russian news site nests articles inside divs or a_tags
    for article in soup.find_all(["div", "article"], class_=re.compile(r"news-item|article-list", re.I)):
        a_tag = article.find("a", href=True)
        if not a_tag:
            continue
            
        url = _normalise_url(a_tag["href"], base_url)
        if not url or url in seen:
            continue
            
        # The headline might be in an h3, h4, or just a span
        h_tag = article.find(["h1", "h2", "h3", "h4", "span"], class_=re.compile(r"title|name|headline", re.I))
        headline = h_tag.get_text(strip=True) if h_tag else a_tag.get_text(strip=True)
        
        # Look for date
        date_hint = None
        d_tag = article.find(["time", "span", "div"], class_=re.compile(r"date|time", re.I))
        if d_tag:
            date_hint = d_tag.get("datetime", d_tag.get_text(strip=True))

        if len(headline) > 15:
            seen.add(url)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})

    # Fallback if specific classes aren't found
    if not results:
        for a_tag in soup.find_all("a", href=True):
            url = _normalise_url(a_tag["href"], base_url)
            if not url or url in seen:
                continue
            if "/news/" not in url or url == base_url or url == "https://neftegaz.ru/news/":
                continue
            if re.search(r"/news/[a-z-]+/$", url):
                continue # category link
            headline = a_tag.get_text(strip=True)
            if len(headline) > 15 and " " in headline:
                seen.add(url)
                results.append({"headline": headline, "url": url, "date_hint": None})

    return results


def _newsfilter_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()
    
    # ── Strategy 1: Look for anchor tags that link to external news sources ──
    # Newsfilter renders headlines as <a> tags pointing to reuters.com, prnewswire.com, etc.
    for a_tag in soup.find_all("a", href=True):
        url = a_tag["href"]
        # Skip internal newsfilter links, search, login, etc.
        if "newsfilter.io" in url or not url.startswith("http"):
            continue
        if len(url) < 30:
            continue
        headline = _clean_newsfilter_headline(a_tag.get_text(strip=True))
        if url not in seen and _is_valid_headline(headline):
            seen.add(url)
            # Try to find a date hint near the anchor (sibling or parent text)
            date_hint = None
            parent = a_tag.parent
            if parent:
                # Look for relative date text like "1D ago", "2h ago" in parent/siblings
                parent_text = parent.get_text(" ", strip=True)
                import re as _re
                date_match = _re.search(r'(\d+[mhDdWw]\s*ago)', parent_text)
                if date_match:
                    date_hint = date_match.group(1)
            results.append({"headline": headline, "url": url, "date_hint": date_hint})
    
    # ── Strategy 2: Fallback to styled spans if Strategy 1 finds nothing ──
    if not results:
        for row in soup.find_all("div", style=re.compile(r"border-bottom", re.I)):
            a_tag = row.find("a", href=True)
            h_span = row.find("span", style=re.compile(r"font-weight: 500", re.I))
            d_span = row.find("span", style=re.compile(r"color: rgb\(153, 153, 153\)", re.I))
            
            if h_span and a_tag:
                headline = h_span.get_text(strip=True)
                url = urljoin(base_url, a_tag["href"])
                date_hint = d_span.get_text(strip=True) if d_span else None
                
                if url not in seen and _is_valid_headline(headline):
                    seen.add(url)
                    results.append({"headline": headline, "url": url, "date_hint": date_hint})
                
    return results


def _sec_edgar_parser(soup: BeautifulSoup, base_url: str) -> list[dict]:
    results = []
    seen = set()

    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 4:
            continue
        form_type = tds[0].get_text(strip=True)
        if "S-1" not in form_type and "S-4" not in form_type:
            continue
            
        company_info = tds[2].get_text(" ", strip=True)
        company_name = company_info.split("(Filer)")[0].strip()
        
        a_tag = tds[1].find("a", href=re.compile(r"index.htm", re.I))
        if not a_tag:
            a_tag = tds[1].find("a", href=True)
            if not a_tag:
                continue
                
        url = urljoin(base_url, a_tag["href"])
        if not url or url in seen:
            continue
            
        date_hint = tds[3].get_text(strip=True)
        headline = f"SEC Registration Statement ({form_type}): {company_name}"
        
        seen.add(url)
        results.append({"headline": headline, "url": url, "date_hint": date_hint})

    return results


def _pick_parser(site_name: str):
    name_lower = site_name.lower()
    if "energy-pedia" in name_lower:
        return _energy_pedia_parser
    if "newsfilter" in name_lower:
        return _newsfilter_parser
    if "upstream" in name_lower or "recharge" in name_lower:
        return _nhst_parser
    if "neftegaz" in name_lower:
        return _neftegaz_parser
    if "edgar" in name_lower or "sec " in name_lower:
        return _sec_edgar_parser
    return _generic_article_parser


def _rss_to_candidates(rss_articles: list[dict]) -> list[dict]:
    results = []
    seen = set()
    for art in rss_articles:
        url = art.get("link", "")
        headline = art.get("title", "")
        if url and url not in seen and _is_valid_headline(headline):
            seen.add(url)
            results.append({
                "headline": headline,
                "url": url,
                "date_hint": art.get("date", None),
            })
    return results


# ─────────────────────────────────────────────────────────────
# Date utilities
# ─────────────────────────────────────────────────────────────

import dateutil.parser as dparser

try:
    from .fetcher import AsyncSmartFetcher, parse_relative_date
except ImportError:
    from fetcher import AsyncSmartFetcher, parse_relative_date

def parse_date(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    # Some sources collapse ISO date and time together, e.g. 2026-04-0106:20:52.
    date_str = re.sub(r"^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})$", r"\1 \2", date_str)
    # Try relative parsing first
    rel = parse_relative_date(date_str)
    if rel != date_str:
        return rel
    try:
        dt = dparser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def is_within_date_range(parsed_date, start_date, end_date):
    if not parsed_date:
        return False
    try:
        from datetime import datetime as dt_cls
        s = dt_cls.strptime(start_date, "%Y-%m-%d").date()
        e = dt_cls.strptime(end_date, "%Y-%m-%d").date()
        p = dt_cls.strptime(parsed_date, "%Y-%m-%d").date()
        return s <= p <= e
    except Exception:
        return False


def _detect_language(text: str) -> str:
    try:
        from langdetect import detect
        return detect(text[:1000])
    except Exception:
        return "unknown"


# ─────────────────────────────────────────────────────────────
# Main Async Scraper Class
# ─────────────────────────────────────────────────────────────

class AsyncMAScraper:

    def __init__(
        self,
        start_date: str,
        end_date: str,
        headless: bool = True,
        max_workers: int = 4,
        enable_aggregator: bool = True,
        site_filter: list[str] | None = None,
        browser_only: bool = False,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.headless = headless
        self.max_workers = max_workers
        self.browser_only = bool(browser_only)
        self.extractor = DealExtractor()
        self.budget_mode = getattr(self.extractor.ai, "budget_mode", False)
        self.excel_writer = ExcelReportWriter()
        self.google_sheets = GoogleSheetsManager(credentials_path=str(GOOGLE_CREDENTIALS_PATH))
        self.db = DealDatabase()
        self.seen_cache = SeenCache(Path(SEEN_CACHE_PATH))
        self.source_health = SourceHealthTracker(Path(SOURCE_HEALTH_PATH))

        self.lock = asyncio.Lock()
        self.processed_urls: set = set()
        self.deals: list = []
        self.rejected_deals: list = []
        self.logs: list = []
        self.issues: list = []
        # Browser-only implies "no aggregation" because the aggregator is RSS/Google-News/SEC based.
        self.enable_aggregator = bool(enable_aggregator) and (not self.browser_only)
        self.site_filter = [s.lower() for s in site_filter] if site_filter else None

        # ── Agentic AI Agents (Self-Healing, Query Generation, QA) ──
        if self.budget_mode:
            self.self_healing = None
            self.query_agent = None
            self.qa_agent = None
        else:
            self.self_healing = SelfHealingAgent(self.extractor.ai)
            self.query_agent = QueryGenerationAgent(self.extractor.ai)
            self.qa_agent = CheckMyWorkAgent(self.extractor.ai)

        self.metrics = {
            "Total URLs provided":                len(TARGET_SITES),
            "Total URLs successfully processed":   0,
            "Total URLs — Headline-Only Mode":     0,
            "Total URLs failed / blocked":         0,
            "Total sections/sub-sections scanned": 0,
            "Total articles fetched":              0,
            "Articles within date range":          0,
            "Total M&A deals identified":          0,
            "Deals auto-included (≥ 0.80)":        0,
            "Deals flagged for review (0.50–0.79)": 0,
            "Deals in Review Queue (0.31–0.49)":   0,
            "Deals rejected by AI":                0,
            "Confirmed closed deals (conf = 1.0)": 0,
            "Announced / pending deals":           0,
            "MOUs / LOIs (not yet signed)":        0,
            "Headline-only deals (paywall)":       0,
            "Deals with disclosed value":          0,
            "Total disclosed deal value":          "N/A",
        }

    # ── Async-safe Logging Helpers ──

    async def _log_processing(self, website, status, total_found, in_range, deals_ext,
                        review_items, issues_txt, resolution,
                        method="A", access="Full", render="Static"):
        async with self.lock:
            self.logs.append([
                len(self.logs) + 1, website, "Home/Latest", method, access,
                render, status, total_found, in_range, deals_ext, review_items,
                issues_txt, resolution,
            ])

    async def _log_issue(self, category, desc, website, severity, solution, perm_fix):
        async with self.lock:
            self.issues.append([
                len(self.issues) + 1, category, desc, website,
                severity, solution, perm_fix,
            ])

    async def _update_metric(self, key, increment=1):
        async with self.lock:
            if isinstance(self.metrics[key], int):
                self.metrics[key] += increment

    def _reconcile_metrics(self, active_sites_count: int | None = None) -> None:
        """Recalculate dashboard metrics to match final exported sheets."""
        if active_sites_count is not None:
            self.metrics["Total URLs provided"] = int(active_sites_count)

        total_deals = len(self.deals)
        self.metrics["Total M&A deals identified"] = total_deals
        self.metrics["Deals rejected by AI"] = len(self.rejected_deals)

        auto_included = sum(1 for d in self.deals if float(d.get("Confidence", 0.0)) >= 0.80)
        flagged_review = sum(1 for d in self.deals if 0.50 <= float(d.get("Confidence", 0.0)) < 0.80)
        review_queue = sum(1 for d in self.deals if 0.31 <= float(d.get("Confidence", 0.0)) < 0.50)
        self.metrics["Deals auto-included (≥ 0.80)"] = auto_included
        self.metrics["Deals flagged for review (0.50–0.79)"] = flagged_review
        self.metrics["Deals in Review Queue (0.31–0.49)"] = review_queue

        disclosed = sum(1 for d in self.deals if str(d.get("Value", "Undisclosed")).strip().lower() not in ("undisclosed", "n/a", ""))
        self.metrics["Deals with disclosed value"] = disclosed

        headline_only = sum(1 for d in self.deals if bool(d.get("Is Paywall")))
        self.metrics["Headline-only deals (paywall)"] = headline_only

        closed = sum(1 for d in self.deals if float(d.get("Confidence", 0.0)) >= 0.99)
        announced = sum(1 for d in self.deals if str(d.get("Deal Status", "")).lower() in ("announced", "pending"))
        self.metrics["Confirmed closed deals (conf = 1.0)"] = closed
        self.metrics["Announced / pending deals"] = announced
        mou_loi = sum(1 for d in self.deals if str(d.get("Deal Type", "")).upper() in ("MOU / LOI", "MOU", "LOI"))
        self.metrics["MOUs / LOIs (not yet signed)"] = mou_loi

    # ── Main Entry Point ──

    async def run(self):
        _configure_console_output()
        import aiohttp
        mode_str = "Headed (Visible)" if not self.headless else "Headless Stealth"
        print(f"\n{'='*70}")
        print(f"  ENERGY M&A SCRAPER (ASYNC) │  {self.start_date}  →  {self.end_date}")
        print(f"  Sites: {len(TARGET_SITES)}  │  Workers: {self.max_workers}  │  Mode: {mode_str}")
        print(f"{'='*70}\n")

        sem = asyncio.Semaphore(self.max_workers)

        # ── FIX 3.3: Update SeeNews archive URL to current year ──
        from datetime import datetime
        current_year = datetime.now().year
        for site in TARGET_SITES:
            if "seenews.com/news/archive/" in site.get("url", ""):
                site["url"] = f"https://seenews.com/news/archive/{current_year}"

        # ── Apply site filter if specified ──
        active_sites = TARGET_SITES
        if self.site_filter:
            exact_sites = [
                s for s in TARGET_SITES
                if s["name"].lower() in self.site_filter
            ]
            active_sites = exact_sites or [
                s for s in TARGET_SITES
                if any(f in s["name"].lower() for f in self.site_filter)
            ]
            print(f"  🔍 Filtered to {len(active_sites)} sites: {[s['name'] for s in active_sites]}")

        # ── Source health scoring & deprioritization ──
        if active_sites:
            for site in active_sites:
                score = self.source_health.score(site["name"])
                site["_health_score"] = score
                if self.source_health.deprioritize(site["name"]):
                    site["deprioritized"] = True
            active_sites.sort(key=lambda s: s.get("_health_score", 1.0), reverse=True)

        # ── Collaborative Learning Ingestion ──
        if self.google_sheets.enabled:
            print(f"  Fetching collective intelligence from Google Sheets …")
            if self.site_filter and not active_sites:
                logger.warning(f"No sites matched filter: {self.site_filter}")
                print("  [WARN] No curated sites matched the requested filter.")
            shared_lessons = self.google_sheets.get_feedback_data()
            if shared_lessons:
                self.extractor.ai.load_shared_feedback(shared_lessons)
                print(f"  💡 AI updated with {len(shared_lessons)} lessons from your team.")

        async with aiohttp.ClientSession() as session:
            browser_mgr = AsyncBrowserManager(headless=self.headless)
            await browser_mgr.__aenter__()

            # ── Newsfilter Login ──
            newsfilter_active = any("Newsfilter" in s["name"] for s in active_sites)
            if newsfilter_active:
                nf_email = os.environ.get("NEWSFILTER_EMAIL", "").strip()
                nf_password = os.environ.get("NEWSFILTER_PASSWORD", "").strip()
                if nf_email and nf_password:
                    await browser_mgr.login_newsfilter(nf_email, nf_password)
                else:
                    logger.info("Newsfilter credentials not configured; skipping pre-login.")

            async def _worker(site):
                async with sem:
                    try:
                        # Peak Level Upgrade: Support for Task-Level Timeouts
                        # If a single site takes more than 10 minutes, kill the task to keep the pipeline moving.
                        try:
                            await asyncio.wait_for(self._run_site_internal(site, session, browser_mgr), timeout=600)
                            print(f"   ✓ Finished {site['name']}")
                        except asyncio.TimeoutError:
                            print(f"   ⏱️ TIMEOUT on {site['name']} (exceeded 10 min). Skipping.")
                            logger.error(f"[{site['name']}] Global task timeout exceeded (600s). Abandoned.")
                    except Exception as exc:
                        print(f"   ❌ CRASH on {site['name']}: {exc}")
                        traceback.print_exc()

            tasks = [_worker(site) for site in active_sites]
            await asyncio.gather(*tasks)

            # ── Safe Browser Shutdown ──
            # Playwright aexit can sometimes hang if a context is in a weird state.
            try:
                await asyncio.wait_for(browser_mgr.__aexit__(None, None, None), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("Browser manager shutdown timed out (30s) — continuing anyway.")
            except Exception as e:
                logger.error(f"Error during browser manager shutdown: {e}")

        # ── News Aggregator Layer ──

        if self.enable_aggregator:
            await self._process_aggregated_news()

        # ── Deduplicate deals by normalized URL and by headline similarity ──
        from urllib.parse import urlparse, urlunparse
        seen_urls = set()
        seen_headlines = set()
        unique_deals = []
        for d in self.deals:
            # Strip query params from URL for dedup
            raw_url = d.get("Link", "")
            try:
                parsed = urlparse(raw_url)
                clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
            except Exception:
                clean_url = raw_url
            # Normalize headline: first 50 chars, lowered, stripped
            norm_headline = d.get("Headline", "")[:50].lower().strip()

            if clean_url in seen_urls or (norm_headline and norm_headline in seen_headlines):
                continue  # Skip duplicate
            seen_urls.add(clean_url)
            if norm_headline:
                seen_headlines.add(norm_headline)
            unique_deals.append(d)
        dupes_removed = len(self.deals) - len(unique_deals)
        self.deals = unique_deals

        # ── AGENT 3: Check-My-Work QA Pass ──
        if self.qa_agent:
            print("\n  Running Check-My-Work QA Agent...")
            qa_summary = await self.qa_agent.review_all_deals(self.deals, self.rejected_deals)
        else:
            qa_summary = {"status": "skipped", "reason": "budget mode"}

        # ── Export ──
        # Save self-learning memory before export
        self.extractor.ai.save_memory()
        ai_stats = self.extractor.ai.get_stats_summary()
        self.seen_cache.save()
        self.source_health.save()
        
        # ── AGENT 4: Final Executive Summary ──
        if self.qa_agent:
            print("  ARIA: Generating final executive run summary...")
            run_summary = await self.qa_agent.generate_run_summary(self.deals)
        else:
            run_summary = "AI summary skipped (budget mode)."

        self._reconcile_metrics(active_sites_count=len(active_sites))

        print(f"\n{'='*70}")
        print(f"  Scraping complete — {len(self.deals)} verified M&A deals found.")
        if dupes_removed:
            print(f"  Duplicates removed: {dupes_removed}")
        print(f"  Rejected by AI:   {len(self.rejected_deals)}")
        print(f"  AI Stats:         {ai_stats}")
        if qa_summary.get('fixed', 0) > 0 or qa_summary.get('rescued_from_rejected', 0) > 0:
            print(f"  QA Agent Fixes:   {qa_summary}")
        
        print(f"\n  ARIA SUMMARY:\n  {run_summary}")
        
        print(f"\n  Writing Excel report …")
        self.excel_writer.export(self.deals, self.logs, self.issues, self.metrics,
                                 rejected_deals=self.rejected_deals, ai_stats=ai_stats,
                                 run_summary=run_summary)

        # Optional Google Sheets sync (Excel remains the primary output)
        if self.google_sheets.enabled and self.deals:
            try:
                self.google_sheets.sync_deals(self.deals)
            except Exception as e:
                logger.warning(f"Google Sheets sync failed: {e}")
                print("  [WARN] Google Sheets sync failed; Excel report remains the system of record.")

        # ── Fix 5: Autonomous Self-Correction Feedback File ──
        # Deals with low confidence or keyword-only sheet assignment are flagged here.
        # On the next run, these are force-sent to AI re-classification.
        # User never needs to come back to fix a mis-routed deal manually.
        import json as _json
        feedback = []
        for d in self.deals:
            if d.get("Confidence", 1.0) < 0.80 or d.get("_sheet_was_keyword_default", False):
                feedback.append({
                    "headline": d.get("Headline", ""),
                    "sheet": d.get("Sheet", ""),
                    "confidence": d.get("Confidence", 0.0),
                    "link": d.get("Link", ""),
                    "source": d.get("Source", ""),
                })
        if feedback:
            ensure_runtime_dirs()
            feedback_path = FEEDBACK_DIR / "feedback_needed.json"
            with open(feedback_path, "w", encoding="utf-8") as _f:
                _json.dump(feedback, _f, indent=2)
            print(f"  📋 Feedback file written: {len(feedback)} deals flagged for review → feedback_needed.json")

    # ── Site Processing ──

    async def _run_grounding_fallback(self, name: str, url: str) -> list[dict]:
        """Triggers Google Search fallbacks if the scraper is utterly blocked."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        logger.warning(f"[{name}] Triggering Grounding Fallback for {domain}...")
        
        grounding_query = f"{domain} energy M&A deals {self.start_date} to {self.end_date}"
        grounded_text = await self.extractor.ai.grounding_search(grounding_query)
        candidates = []
        if grounded_text:
            # Parse grounding text as a single synthetic article
            candidates.append({
                "headline": f"Grounding summary for {domain}",
                "url": url,
                "date_hint": self.start_date,
                "grounding_injected": {
                    "headline": f"Grounding summary for {domain}",
                    "body_text": grounded_text
                }
            })
        return candidates

    async def _process_site(self, site: dict, session, browser):
        name = site["name"]
        url = site["url"]
        is_paywall_site = site.get("is_paywall", False)

        logger.info(f"[{name}] Starting async processing...")
        fetcher = AsyncSmartFetcher(browser_manager=browser, session=session, browser_only=self.browser_only)
        html, rss_articles, fetch_method, access_mode, render_type = await fetcher.fetch_listing(site)

        candidates = []
        
        # ── Grounding Agent Fallback for Hard Blocks ──
        # Disabled in browser-only mode (it is a non-browser search/tool fallback).
        if (not self.browser_only) and access_mode in ("Blocked", "Failed") and not rss_articles:
            candidates = await self._run_grounding_fallback(name, url)
            if not candidates:
                await self._update_metric("Total URLs failed / blocked")
                await self._log_processing(name, "❌ Blocked", 0, 0, 0, 0,
                                     f"Access: {access_mode}", "Tried Grounding",
                                     fetch_method, access_mode, render_type)
                await self._log_issue("Access Blocked", f"Fetch failed — {access_mode}", name,
                                "HIGH", "Grounding Failed", "Proxy")
                self.source_health.update(name, access_mode, "❌ Blocked", 0)
                return
            else:
                access_mode = "Google-Grounding"
                fetch_method = "Gemini Search Tool"

        await self._update_metric("Total URLs successfully processed")
        await self._update_metric("Total sections/sub-sections scanned")

        if access_mode == "Headline-Only" or is_paywall_site:
            await self._update_metric("Total URLs — Headline-Only Mode")
            await self._log_issue("Paywall / Auth Block", "Headline-Only mode",
                            name, "MEDIUM", "Headline-Only", "Credentials")

        if rss_articles and not candidates:
            candidates.extend(_rss_to_candidates(rss_articles))

        if html and not candidates:
            soup = BeautifulSoup(html, "html.parser")
            parser_fn = _pick_parser(name)
            html_cands = parser_fn(soup, url)
            
            # ── Retry with Browser if Static returned NO articles ──
            if not html_cands and render_type != "JS" and browser and browser.available:
                logger.warning(f"[{name}] Static fetch returned 0 articles. Forcing Render Retry with Browser...")
                html = await browser.fetch_page(url, wait_seconds=4.0, pagination_type=site.get("pagination_type"), max_pages=site.get("max_pages", 3))
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    html_cands = parser_fn(soup, url)
                    fetch_method = "Browser-Retry"
                    render_type = "JS"
                    access_mode = "Full"

            existing_urls = {c["url"] for c in candidates}
            for c in html_cands:
                if c["url"] not in existing_urls:
                    candidates.append(c)

        if not candidates:
            # ── AGENT 1: Self-Healing Selector Discovery ──
            # When the generic parser finds 0 articles but we got valid HTML,
            # ask the AI to discover the correct CSS selectors.
            if self.self_healing and html and len(html) > 500:
                logger.info(f"[{name}] Self-Healing: Attempting AI selector discovery...")
                selectors = await self.self_healing.discover_selectors(name, html)
                if selectors and selectors.get("confidence", 0) >= 0.5:
                    soup = BeautifulSoup(html, "html.parser")
                    healed_cands = self.self_healing.parse_with_discovered_selectors(soup, url, selectors)
                    if healed_cands:
                        candidates.extend(healed_cands)
                        print(f"   Self-Healed: Found {len(healed_cands)} articles with AI-discovered selectors")
                        fetch_method = "Self-Healed"

        if not candidates:
            await self._log_processing(name, "⚠ Partial", 0, 0, 0, 0,
                                 "No candidates", "None",
                                 fetch_method, access_mode, render_type)
            self.source_health.update(name, access_mode, "⚠ Partial", 0)
            return

        site_articles_found = len(candidates)
        site_in_range = 0
        site_deals = 0
        site_reviews = 0
        await self._update_metric("Total articles fetched", site_articles_found)

        # Rate-limit guard: 4 concurrent candidate processors avoids Groq 429 bursts
        cand_sem = asyncio.Semaphore(4)
        is_newsfilter_ma = "newsfilter" in name.lower() and "m&a" in name.lower()
        is_newsfilter = "newsfilter" in name.lower()
        is_sec_edgar = "edgar" in name.lower() or "sec " in name.lower()

        print(f"   ↳ {name}: {site_articles_found} candidates to process")

        async def _process_cand(cand):
            nonlocal site_in_range, site_deals, site_reviews
            async with cand_sem:
                headline = cand["headline"]
                article_url = cand["url"]
                date_hint = cand.get("date_hint")
                grounded_data = cand.get("grounding_injected", None)
                final_headline = headline
                
                # Native Translation MUST happen before signal filtering
                if site.get("translate") and not grounded_data:
                    logger.debug(f"[{name}] Translating native headline...")
                    # We use the existing headline translation for the first pass
                    headline = await self.extractor.ai.translate_foreign_headline(headline)
                    cand["headline"] = headline
                    logger.info(f"[{name}] Translated headline: {headline[:60]}")
                    final_headline = headline

                if self.seen_cache.is_seen(article_url, headline):
                    return

                async with self.lock:
                    if article_url in self.processed_urls:
                        return
                    self.processed_urls.add(article_url)

                # Parse relative dates from Newsfilter ('2D ago' → ISO)
                p_date = None
                if date_hint:
                    p_date = _parse_relative_date(date_hint) or parse_date(date_hint)
                
                # Fail-proof URL Date Extraction (Rigzone etc)
                if not p_date and article_url:
                    import re as _re
                    # Extract date from formats like /2026/03/28/ or -28-mar-2026-
                    date_match = _re.search(r'/(20\d{2})/(\d{2})/(\d{2})/', article_url)
                    if date_match:
                        p_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                    else:
                        date_match2 = _re.search(r'-(\d{1,2})-([a-z]{3})-(20\d{2})-', article_url, _re.IGNORECASE)
                        if date_match2:
                            p_date = parse_date(f"{date_match2.group(1)} {date_match2.group(2)} {date_match2.group(3)}")

                if p_date and not is_within_date_range(p_date, self.start_date, self.end_date):
                    return

                # Newsfilter M&A page already pre-filters for M&A → skip signal check
                # SEC S-1 pages don't explicitly say "merger", so we bypass the keyword signal filter
                if not grounded_data and not is_newsfilter_ma and not is_sec_edgar and not _headline_has_ma_signal(headline):
                    return  # Skip completely non-M&A/non-structural headlines

                # Local SQLite Deal Deduplication
                if self.db.deal_exists(headline):
                    logger.debug(f"[{name}] Skipped previously processed deal: {headline[:60]}")
                    return

                # Persistent cache to avoid reprocessing across runs
                self.seen_cache.mark(article_url, headline)

                body_text = ""
                final_headline = headline
                is_paywall = is_paywall_site

                if grounded_data:
                    # Bypass individual fetching for grounding injected results
                    final_headline = grounded_data.get("headline", headline)
                    body_text = grounded_data.get("body_text", final_headline)  # Use AI summary for extraction
                    if not p_date:
                        p_date = self.start_date
                elif not is_paywall_site:
                    a_html, a_access, _ = await fetcher.fetch_article(
                        article_url, needs_js=site.get("needs_js", False)
                    )
                    is_paywall = a_access == "Headline-Only"

                    if a_html and a_access not in ("Blocked", "Failed"):
                        art_headline, art_date, art_body = self.extractor.extract_article_metadata(a_html)
                        body_text = art_body

                        if _is_valid_headline(art_headline):
                            final_headline = art_headline
                        elif "robot" in final_headline.lower() or "captcha" in final_headline.lower() or "forbidden" in final_headline.lower():
                            # Fallback to URL slug for blocked sites like Bloomberg
                            slug = article_url.split("/")[-1].split("?")[0]
                            final_headline = slug.replace("-", " ").title()

                        if not p_date and art_date:
                            p_date = parse_date(art_date)

                        lang = _detect_language(art_body[:500])
                        # Peak Level: Full-body translation for international sources
                        if site.get("translate_body") and lang not in ("en", "unknown") and len(art_body) > 100:
                            logger.info(f"[{name}] Performing high-fidelity full-body translation...")
                            translated_body = await self.extractor.ai.translate_full_body(art_body)
                            if translated_body:
                                body_text = translated_body
                                logger.info(f"[{name}] Full-body translation complete ({len(body_text)} chars)")
                        elif lang not in ("en", "unknown") and len(final_headline) > 10:
                            body_text = art_body[:500]

                if not p_date:
                    # Only log if date_hint existed but failed to parse (not just absent)
                    if date_hint:
                        await self._log_issue("Date Parse Failure", f"Could not parse: {str(date_hint)[:40]}", name, "LOW",
                                        "Assumed in-range", "Site parser")
                    p_date = self.start_date

                if not is_within_date_range(p_date, self.start_date, self.end_date):
                    return

                async with self.lock:
                    site_in_range += 1
                await self._update_metric("Articles within date range")

                confidence = self.extractor.compute_confidence(final_headline, body_text, is_paywall)

                # Phase 1 Fix: SEC S-1/S-4 filings are high-conviction by definition → force confidence 1.0
                if is_sec_edgar:
                    confidence = 1.0
                    logger.info(f"[{name}] SEC filing detected — confidence forced to 1.0: {final_headline[:60]}")

                if confidence < 0.15 and not grounded_data:
                    return

                # Newsfilter M&A page is pre-filtered → skip energy check
                # SEC filings bypass energy relevance check (they are inherently registration events)
                if not grounded_data and not is_newsfilter_ma and not is_sec_edgar and not is_energy_relevant(final_headline, body_text):
                    logger.debug(f"[{name}] Rejected (non-energy): {final_headline[:60]}")
                    return

                # Early hard-reject gate (conservative) to avoid AI spend on obvious non-deals
                if not grounded_data and not is_newsfilter_ma and not is_sec_edgar and confidence < 0.60:
                    early_reason = self.extractor.ai.early_reject_reason(final_headline, body_text[:800])
                    if early_reason:
                        industry, sector = self.extractor.determine_industry(final_headline + " " + body_text)
                        deal_record = {
                            "Headline": final_headline,
                            "Buyer": "Unknown",
                            "Seller": "Unknown",
                            "Asset": "Unknown",
                            "Date": p_date or self.start_date,
                            "Industry": industry,
                            "Sector": sector,
                            "Link": article_url,
                            "Geography": "Global",
                            "Value": "Undisclosed",
                            "Deal Type": "Rejected/Other",
                            "Deal Status": "Rejected/Other",
                            "Strategic Rationale": "Hard reject (pre-AI)",
                            "Confidence": confidence,
                            "Source": name,
                            "Sheet": "Reports",
                            "Rejection Reason": early_reason,
                        }
                        async with self.lock:
                            self.rejected_deals.append(deal_record)
                        await self._update_metric("Deals rejected by AI")
                        logger.info(f"[{name}] 🛑 Early hard-reject: {final_headline[:60]} — {early_reason}")
                        return

                # ── Extract entities (Buyer, Seller, Asset, Value, etc.) ──
                entities = await self.extractor.extract_deal_entities(final_headline, body_text)
                
                # ── Classify into industry sheet ──
                # Tier 1: keyword classifier (runs BEFORE AI — free)
                industry, sector = self.extractor.determine_industry(final_headline + " " + body_text)
                sheet, confident = classify_deal_sheet(final_headline, body_text, industry, sector)

                # Hard reject: non-energy sector caught by blocklist — skip before any AI call
                if sheet == "REJECT":
                    logger.info(f"[{name}] ⛔ Hard-rejected (non-energy sector): {final_headline[:60]}")
                    return

                deal_record = {
                    "Headline": final_headline,
                    "Buyer": entities.get("buyer", "Unknown"),
                    "Seller": entities.get("seller", "Unknown"),
                    "Asset": entities.get("asset", "Unknown"),
                    "Date": p_date or self.start_date,
                    "Industry": industry,
                    "Sector": sector,
                    "Link": article_url,
                    "Geography": entities.get("geography", "Global"),
                    "Value": self.extractor.ai.normalize_value_to_usd(entities.get("value", "Undisclosed")),
                    "Deal Type": entities.get("deal_type", "M&A"),
                    "Deal Status": entities.get("deal_status", "Announced"),
                    "Strategic Rationale": entities.get("strategic_rationale", "No rationale provided"),
                    "Confidence": confidence,
                    "Source": name,
                    "Sheet": sheet,
                    "Is Paywall": bool(is_paywall),
                }

                # ── AI Verification Gate ──
                # SEC filings bypass AI rejection gate — they are always high-value events
                if self.extractor.ai.enabled and not grounded_data and not is_sec_edgar:
                    verdict = await self.extractor.ai.verify_is_deal(final_headline, body_text[:2000])
                    if not verdict["is_deal"]:
                        deal_record["Rejection Reason"] = verdict["reason"]
                        async with self.lock:
                            self.rejected_deals.append(deal_record)
                        await self._update_metric("Deals rejected by AI")
                        logger.info(f"[{name}] 🔴 AI-REJECTED [{confidence:.2f}] {final_headline[:60]} — {verdict['reason'][:50]}")
                        return

                    # ── Use AI-assigned sheet if AI returned one (overrides keyword classifier) ──
                    ai_sheet = verdict.get("sheet", "").strip()
                    valid_sheets = {"Upstream", "Midstream", "OFS", "R&M", "P&U", "JV & Partnerships", "Reports"}
                    if ai_sheet in valid_sheets:
                        if ai_sheet != sheet:
                            logger.info(f"[{name}] 🧠 AI overrides sheet: '{sheet}' → '{ai_sheet}' for: {final_headline[:50]}")
                        sheet = ai_sheet
                        deal_record["Sheet"] = sheet
                        confident = True

                    # If AI fail-safe triggered (all providers down), lower confidence → Review Queue
                    if verdict.get("_fail_safe"):
                        confidence = 0.40
                        deal_record["Confidence"] = 0.40

                # ── Self-Learning: Remember confirmed deal companies ──
                self.extractor.ai.learn_from_deal(deal_record)

                # ── Local DB Persistence ──
                self.db.insert_deal(deal_record)

                async with self.lock:
                    self.deals.append(deal_record)

                await self._update_metric("Total M&A deals identified")

                if deal_record["Value"] != "Undisclosed":
                    await self._update_metric("Deals with disclosed value")
                if deal_record["Deal Type"] == "MOU / LOI":
                    await self._update_metric("MOUs / LOIs (not yet signed)")

                if confidence >= 0.80 or grounded_data:
                    await self._update_metric("Deals auto-included (≥ 0.80)")
                    async with self.lock:
                        site_deals += 1
                    tag = "🟢"
                elif confidence >= 0.50:
                    await self._update_metric("Deals flagged for review (0.50–0.79)")
                    async with self.lock:
                        site_deals += 1
                    tag = "🟡"
                else:
                    await self._update_metric("Deals in Review Queue (0.31–0.49)")
                    async with self.lock:
                        site_reviews += 1
                    tag = "🟠"

                if is_paywall:
                    await self._update_metric("Headline-only deals (paywall)")

                logger.info(f"[{name}] {tag} [{confidence:.2f}] {final_headline[:80]}")

        async def _safe_process_cand(cand):
            """Wraps _process_cand with a 90s timeout so one stuck AI call
            cannot freeze the entire candidate batch for a site."""
            try:
                await asyncio.wait_for(_process_cand(cand), timeout=90)
            except asyncio.TimeoutError:
                headline_short = cand.get('headline', '')[:60]
                logger.warning(f"[{name}] Candidate timeout (90s): {headline_short}")
            except Exception as e:
                logger.error(f"[{name}] Candidate error: {e}")

        if candidates:
            await asyncio.gather(*[_safe_process_cand(cand) for cand in candidates])

        status = "✅ Processed" if site_articles_found > 0 else "⚠ Partial"
        if access_mode == "Google-Grounding":
            status = "✅ Grounded"

        await self._log_processing(name, status, site_articles_found,
                             site_in_range, site_deals, site_reviews,
                             "None", "None", fetch_method, access_mode, render_type)
        self.source_health.update(name, access_mode, status, site_articles_found)
        logger.info(f"[{name}] Done — {site_in_range} in range │ {site_deals} deals │ {site_reviews} review")

    # ── News Aggregator Processing ──

    async def _process_aggregated_news(self):
        """Run the multi-source news aggregator and process candidates."""
        import aiohttp

        print(f"\n{'─'*70}")
        print(f"  📡 AGGREGATOR LAYER — Scanning wire services, Google News, SEC EDGAR…")
        print(f"{'─'*70}")

        aggregator = AsyncNewsAggregator(
            start_date=self.start_date,
            end_date=self.end_date,
            already_processed={u.split('?')[0].rstrip('/').lower() for u in self.processed_urls},
        )

        # ── AGENT 2: AI-Generated Supplementary Queries ──
        if self.query_agent:
            try:
                print("  Query Agent: Generating supplementary search queries...")
                extra_queries = await self.query_agent.generate_supplementary_queries(
                    self.start_date, self.end_date,
                    existing_deals=self.deals,
                )
                if extra_queries:
                    try:
                        from .news_aggregator import GOOGLE_NEWS_MA_QUERIES
                    except ImportError:
                        from news_aggregator import GOOGLE_NEWS_MA_QUERIES
                    for q in extra_queries:
                        if q not in GOOGLE_NEWS_MA_QUERIES:
                            GOOGLE_NEWS_MA_QUERIES.append(q)
                    print(f"  Query Agent: Added {len(extra_queries)} AI-generated queries")
            except Exception as e:
                logger.warning(f"QueryGen integration failed (non-fatal): {e}")

        candidates = await aggregator.collect_all()

        if not candidates:
            print("  Aggregator: No new candidates found.")
            return

        print(f"  Aggregator: Processing {len(candidates)} unique candidates...")
        agg_deals = 0
        agg_rejected = 0
        agg_in_range = 0

        # Trusted wire sources where headlines are self-contained (no body fetch needed)
        _TRUSTED_WIRE_PREFIXES = ("pr newswire", "globenewswire", "businesswire",
                                   "sec edgar", "oilandgas360", "renewablesnow", "rigzone")

        async with aiohttp.ClientSession() as session:
            fetcher = AsyncSmartFetcher(browser_manager=None, session=session, browser_only=self.browser_only)

            cand_sem = asyncio.Semaphore(25)  # Increased from 10 for speed

            async def _process_agg_cand(cand):
                nonlocal agg_in_range, agg_deals, agg_rejected
                async with cand_sem:
                    headline = cand["headline"]
                    article_url = cand["url"]
                    date_hint = cand.get("date_hint")
                    source = cand.get("source", "Aggregator")

                    if self.seen_cache.is_seen(article_url, headline):
                        return

                    # Dedup against already-processed
                    async with self.lock:
                        if article_url in self.processed_urls:
                            return
                        self.processed_urls.add(article_url)

                    # Local SQLite Deal Deduplication
                    if self.db.deal_exists(headline):
                        return

                    # Date check
                    p_date = parse_date(date_hint) if date_hint else None
                    if p_date and not is_within_date_range(p_date, self.start_date, self.end_date):
                        return

                    # Quick M&A signal check on headline
                    if not _headline_has_ma_signal(headline):
                        return

                    self.seen_cache.mark(article_url, headline)

                    # SPEED FIX: Skip body fetch for trusted wire service sources
                    # Wire service headlines are self-contained and rich enough for AI extraction
                    is_trusted = any(p in source.lower() for p in _TRUSTED_WIRE_PREFIXES)
                    body_text = ""
                    final_headline = headline

                    if not is_trusted:
                        # Only fetch body for Google News / non-wire candidates
                        try:
                            a_html, a_access, _ = await fetcher.fetch_article(
                                article_url, needs_js=False
                            )
                            if a_html and a_access not in ("Blocked", "Failed"):
                                art_headline, art_date, art_body = self.extractor.extract_article_metadata(a_html)
                                body_text = art_body
                                if art_headline and len(art_headline) > 15 and " " in art_headline:
                                    if "robot" not in art_headline.lower() and "captcha" not in art_headline.lower():
                                        final_headline = art_headline
                                if not p_date and art_date:
                                    p_date = parse_date(art_date)
                        except Exception:
                            pass  # Use headline-only mode

                    if not p_date:
                        p_date = self.start_date

                    if not is_within_date_range(p_date, self.start_date, self.end_date):
                        return

                    async with self.lock:
                        agg_in_range += 1
                    await self._update_metric("Articles within date range")

                    confidence = self.extractor.compute_confidence(final_headline, body_text, is_trusted)
                    if confidence < 0.15:
                        return

                    # Relaxed energy check for trusted energy-specific sources
                    if not is_trusted and not is_energy_relevant(final_headline, body_text):
                        return

                    industry, sector = self.extractor.determine_industry(final_headline + " " + body_text)
                    entities = await self.extractor.extract_deal_entities(final_headline, body_text)

                    deal_record = {
                        "Headline": final_headline,
                        "Buyer": entities.get("buyer", "Unknown"),
                        "Seller": entities.get("seller", "Unknown"),
                        "Asset": entities.get("asset", "Unknown"),
                        "Date": p_date,
                        "Industry": industry,
                        "Sector": sector,
                        "Link": article_url,
                        "Geography": entities.get("geography", "Global"),
                        "Value": entities.get("value", "Undisclosed"),
                        "Deal Type": entities.get("deal_type", "M&A"),
                        "Deal Status": entities.get("deal_status", "Announced"),
                        "Strategic Rationale": entities.get("strategic_rationale", "No rationale provided"),
                        "Confidence": confidence,
                        "Source": source,
                    }

                    # ── Classify into industry sheet (Tier 1: keywords, Tier 2: AI) ──
                    sheet, confident = classify_deal_sheet(final_headline, body_text, industry, sector)
                    if not confident and self.extractor.ai.enabled:
                        sheet = await self.extractor.ai.classify_deal_sector(
                            final_headline, body_text, entities.get("asset", ""), industry, sector
                        )
                    deal_record["Sheet"] = sheet

                    # ── Normalize value to USD ──
                    deal_record["Value"] = self.extractor.ai.normalize_value_to_usd(deal_record["Value"])

                    # ── AI Verification Gate ──
                    if self.extractor.ai.enabled:
                        verdict = await self.extractor.ai.verify_is_deal(final_headline, body_text[:2000])
                        if not verdict["is_deal"]:
                            deal_record["Rejection Reason"] = verdict["reason"]
                            async with self.lock:
                                self.rejected_deals.append(deal_record)
                                agg_rejected += 1
                            await self._update_metric("Deals rejected by AI")
                            logger.info(f"[Aggregator/{source[:20]}] 🔴 AI-REJECTED [{confidence:.2f}] {final_headline[:60]}")
                            return

                    # ── Self-Learning: Remember confirmed deal companies ──
                    self.extractor.ai.learn_from_deal(deal_record)

                    # ── Local DB Persistence ──
                    self.db.insert_deal(deal_record)

                    async with self.lock:
                        self.deals.append(deal_record)
                        agg_deals += 1

                    await self._update_metric("Total M&A deals identified")

                    if deal_record["Value"] != "Undisclosed":
                        await self._update_metric("Deals with disclosed value")
                    if deal_record["Deal Type"] == "MOU / LOI":
                        await self._update_metric("MOUs / LOIs (not yet signed)")

                    if confidence >= 0.80:
                        await self._update_metric("Deals auto-included (≥ 0.80)")
                        tag = "🟢"
                    elif confidence >= 0.50:
                        await self._update_metric("Deals flagged for review (0.50–0.79)")
                        tag = "🟡"
                    else:
                        await self._update_metric("Deals in Review Queue (0.31–0.49)")
                        tag = "🟠"

                    logger.info(f"[Aggregator/{source[:20]}] {tag} [{confidence:.2f}] {final_headline[:80]}")

            if candidates:
                await asyncio.gather(*[_process_agg_cand(cand) for cand in candidates])

        await self._log_processing(
            "📡 Aggregator Layer", "✅ Processed",
            len(candidates), agg_in_range, agg_deals, 0,
            "None", "None", "RSS+GoogleNews+SEC", "Full", "Static"
        )
        print(f"  ✅ Aggregator: {agg_deals} deals found, {agg_rejected} rejected by AI, {agg_in_range} in date range")

    async def _run_site_internal(self, site, session, browser_mgr):
        """Helper to run a site and its secondary paths in the worker."""
        base_url = site["url"]
        paths = [base_url] + site.get("secondary_paths", [])
        
        for current_url in paths:
            modified_site = site.copy()
            modified_site["url"] = current_url
            if current_url != base_url:
                logger.info(f"[{site['name']}] Scanning secondary high-yield path: {current_url}")
            
            await self._process_site(modified_site, session, browser_mgr)
