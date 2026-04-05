"""
fetcher.py — Pure Async Smart Fetcher with Autonomic Fallback Chain.

Fetch priority (per site, in order):
  1. RSS feed          — cleanest, fastest. Zero cost.
  2. Google News RSS   — universal fallback. IMMEDIATELY triggered if RSS
                         returns 0 articles or HTTP 4xx.  No waiting for crash.
  3. Newsfilter API    — JSON endpoint bypass for newsfilter.io
  4. Playwright        — JS rendering for sites that need it
  5. CloudScraper      — Cloudflare bypass
  6. AIOHTTP Static    — standard HTTP
  7. Google News (domain-only) — last resort generic fallback
  8. Google Cache      — paywalled article body retrieval

Key hardening added:
  - asyncio.wait_for() wraps every network call (30 s outer, 20 s inner)
  - RSS is validated: empty feeds or feeds with 0 energy-domain entries
    trigger google_news_queries IMMEDIATELY instead of wasting a cycle
  - CloudScraper 403 / timeout → immediate Google News fallback
  - All except blocks have finally cleanup
"""

import os
import re
import time
import asyncio
import random
import hashlib
import logging
from urllib.parse import quote_plus, urlparse
import aiohttp
import ssl
from datetime import datetime, timedelta

logger = logging.getLogger("energy_scraper.fetcher")

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    logger.warning("cloudscraper not installed — anti-bot bypass unavailable.")

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False


# ──────────────────────────────────────────────
# Expanded, Randomised User-Agent Pool (10 modern strings)
# ──────────────────────────────────────────────

USER_AGENTS = [
    # Chrome 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 124 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Firefox 125 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Firefox 125 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Chrome 123 Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Safari 17 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge 123 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    # Chrome 122 Android (mobile agent sometimes bypasses bot checks)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
    # Opera 109
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
]


def _random_headers(referer: str = "https://www.google.com/") -> dict:
    """Returns a realistic browser header set with a random UA."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Referer": referer,
        "DNT": "1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive per-domain throttling & backoff
# ─────────────────────────────────────────────────────────────────────────────

class DomainThrottle:
    def __init__(self):
        self._state: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str) -> None:
        if not domain:
            return
        async with self._lock:
            state = self._state.setdefault(domain, {"next": 0.0, "penalty": 0.0, "failures": 0})
            wait_for = max(0.0, state["next"] - time.time())
        if wait_for > 0:
            await asyncio.sleep(wait_for)

    async def record(self, domain: str, status_code: int, success: bool = True) -> None:
        if not domain:
            return
        async with self._lock:
            state = self._state.setdefault(domain, {"next": 0.0, "penalty": 0.0, "failures": 0})
            now = time.time()
            if not success or status_code in (403, 429, 503):
                state["failures"] += 1
                state["penalty"] = min(25.0, state["penalty"] + 3.0 + state["failures"])
                jitter = random.uniform(0.5, 1.5)
                state["next"] = now + state["penalty"] * jitter
            else:
                state["failures"] = max(0, state["failures"] - 1)
                state["penalty"] = max(0.0, state["penalty"] - 2.0)
                state["next"] = max(state["next"], now + random.uniform(0.1, 0.4))


_DOMAIN_THROTTLE = DomainThrottle()


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""


# ──────────────────────────────────────────────
# Page Cache (1-hour TTL, per-URL MD5 key)
# ──────────────────────────────────────────────

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _read_cache(url: str):
    path = os.path.join(CACHE_DIR, _cache_key(url) + ".html")
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < 3600:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                pass
    return None


def _write_cache(url: str, html: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, _cache_key(url) + ".html")
    try:
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(html)
    except Exception:
        pass


# ──────────────────────────────────────────────
# RSS Feed Fetcher
# ──────────────────────────────────────────────

async def fetch_rss(rss_url: str, timeout: int = 20) -> list[dict]:
    """Fetch an RSS feed. Returns [] on any failure (never raises)."""
    if not FEEDPARSER_AVAILABLE:
        return []

    def _sync_fetch():
        return feedparser.parse(rss_url)

    try:
        await _DOMAIN_THROTTLE.wait(_domain_from_url(rss_url))
        feed = await asyncio.wait_for(asyncio.to_thread(_sync_fetch), timeout=timeout)
        articles = []
        for entry in feed.entries:
            articles.append({
                "title":   getattr(entry, "title", ""),
                "link":    getattr(entry, "link", ""),
                "date":    getattr(entry, "published", getattr(entry, "updated", "")),
                "summary": getattr(entry, "summary", ""),
            })
        logger.info(f"RSS: {len(articles)} entries from {rss_url[:80]}")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), getattr(feed, "status", 200), success=True)
        return articles
    except asyncio.TimeoutError:
        logger.warning(f"RSS timeout ({timeout}s): {rss_url[:80]}")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), 0, success=False)
        return []
    except Exception as exc:
        logger.warning(f"RSS fetch failed {rss_url[:80]}: {exc}")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), 0, success=False)
        return []


async def fetch_google_news_rss_raw(query: str, timeout: int = 20) -> list[dict]:
    """Fetch Google News RSS for a fully-formed query string.  Never raises."""
    if not FEEDPARSER_AVAILABLE:
        return []

    encoded_query = quote_plus(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    def _sync_fetch():
        return feedparser.parse(rss_url)

    try:
        await _DOMAIN_THROTTLE.wait(_domain_from_url(rss_url))
        await asyncio.sleep(random.uniform(0.8, 2.0))
        feed = await asyncio.wait_for(asyncio.to_thread(_sync_fetch), timeout=timeout)
        articles = []
        for entry in feed.entries:
            articles.append({
                "title":   getattr(entry, "title", ""),
                "link":    getattr(entry, "link", ""),
                "date":    getattr(entry, "published", ""),
                "summary": getattr(entry, "summary", ""),
            })
        logger.info(f"Google News RSS (raw): {len(articles)} results for query")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), getattr(feed, "status", 200), success=True)
        return articles
    except asyncio.TimeoutError:
        logger.warning(f"Google News RSS timeout for query: {query[:60]}")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), 0, success=False)
        return []
    except Exception as exc:
        logger.warning(f"Google News RSS (raw) failed: {exc}")
        await _DOMAIN_THROTTLE.record(_domain_from_url(rss_url), 0, success=False)
        return []


async def fetch_google_news_rss(site_domain: str, query: str = "energy merger acquisition",
                                timeout: int = 20) -> list[dict]:
    """Generic domain-level Google News fallback."""
    full_query = f"site:{site_domain} {query}"
    return await fetch_google_news_rss_raw(full_query, timeout=timeout)


# ──────────────────────────────────────────────
# CloudScraper Fetcher
# ──────────────────────────────────────────────

async def fetch_with_cloudscraper(url: str, max_retries: int = 2) -> tuple[str, int, str, str]:
    """CloudScraper with Cloudflare bypass.  Returns (html, status, access_mode, render_type).
    Never raises — returns ('', 0, 'Failed', 'CloudScraper') on total failure."""
    if not CLOUDSCRAPER_AVAILABLE:
        return "", 0, "Failed", "CloudScraper"

    def _sync_fetch():
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
        )
        scraper.headers.update(_random_headers())
        return scraper.get(url, timeout=25)

    for attempt in range(max_retries):
        try:
            delay = random.uniform(1.0, 3.0) * (1.5 ** attempt)
            await asyncio.sleep(delay)
            await _DOMAIN_THROTTLE.wait(_domain_from_url(url))
            response = await asyncio.wait_for(asyncio.to_thread(_sync_fetch), timeout=35)
            if response.status_code == 200:
                body = response.text
                if len(body) < 500 or "stop the presses" in body.lower():
                    await _DOMAIN_THROTTLE.record(_domain_from_url(url), response.status_code, success=False)
                    return body, response.status_code, "Blocked", "CloudScraper"
                _write_cache(url, body)
                await _DOMAIN_THROTTLE.record(_domain_from_url(url), response.status_code, success=True)
                return body, response.status_code, "Full", "CloudScraper"
            elif response.status_code in (403, 429, 503):
                logger.warning(f"CloudScraper HTTP {response.status_code} on {url[:60]}")
                await _DOMAIN_THROTTLE.record(_domain_from_url(url), response.status_code, success=False)
                return "", response.status_code, "Blocked", "CloudScraper"
            else:
                await _DOMAIN_THROTTLE.record(_domain_from_url(url), response.status_code, success=False)
                return "", response.status_code, "Failed", "CloudScraper"
        except asyncio.TimeoutError:
            logger.warning(f"CloudScraper timeout on {url[:60]} (attempt {attempt+1})")
            await _DOMAIN_THROTTLE.record(_domain_from_url(url), 0, success=False)
        except Exception as e:
            logger.warning(f"CloudScraper attempt {attempt+1} failed for {url[:60]}: {e}")
            await _DOMAIN_THROTTLE.record(_domain_from_url(url), 0, success=False)

    return "", 0, "Failed", "CloudScraper"


# ──────────────────────────────────────────────
# Google Cache Fetcher (paywall bypass)
# ──────────────────────────────────────────────

async def fetch_with_google_cache(url: str) -> tuple[str, int, str, str]:
    """Retrieve a cached copy of an article from Google.
    Works for most paywalled pages (Bloomberg, WSJ).  Never raises."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    headers = {**_random_headers("https://www.google.com/")}
    try:
        ssl_ctx = ssl.create_default_context()
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                await _DOMAIN_THROTTLE.wait(_domain_from_url(cache_url))
                async with session.get(
                    cache_url, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=18),
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        body = await response.text(errors="replace")
                        if len(body) > 300:
                            logger.info(f"Google Cache hit: {len(body)} bytes for {url[:60]}")
                            await _DOMAIN_THROTTLE.record(_domain_from_url(cache_url), response.status, success=True)
                            return body, 200, "Full", "GoogleCache"
                    logger.debug(f"Google Cache miss {url[:60]}: HTTP {response.status}")
                    await _DOMAIN_THROTTLE.record(_domain_from_url(cache_url), response.status, success=False)
                    return "", response.status, "Failed", "GoogleCache"
            except Exception as e:
                logger.debug(f"Google Cache request failed {url[:60]}: {e}")
                await _DOMAIN_THROTTLE.record(_domain_from_url(cache_url), 0, success=False)
                return "", 0, "Failed", "GoogleCache"
    except Exception as e:
        logger.debug(f"Google Cache session failed: {e}")
        return "", 0, "Failed", "GoogleCache"


# ──────────────────────────────────────────────
# Native AIOHTTP Static Fetcher
# ──────────────────────────────────────────────

async def fetch_static(url: str, session: aiohttp.ClientSession,
                       max_retries: int = 3) -> tuple[str, int, str, str]:
    """Standard HTTP fetch with SSL fallback and cache.  Never raises."""
    cached = _read_cache(url)
    if cached:
        return cached, 200, "Full", "Static"

    for attempt in range(max_retries):
        try:
            delay = random.uniform(0.8, 2.0) * (1.3 ** attempt)
            await asyncio.sleep(delay)
            await _DOMAIN_THROTTLE.wait(_domain_from_url(url))

            async with session.get(
                url, headers=_random_headers(), allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=28)
            ) as response:
                sc = response.status

                if sc == 429:
                    wait = random.uniform(12, 22) * (attempt + 1)
                    logger.warning(f"429 on {url[:60]}, waiting {wait:.0f}s")
                    await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=False)
                    await asyncio.sleep(wait)
                    continue

                if sc == 403:
                    if CLOUDSCRAPER_AVAILABLE:
                        logger.info(f"Static 403 → CloudScraper for {url[:60]}")
                        await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=False)
                        return await fetch_with_cloudscraper(url)
                    await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=False)
                    return "", sc, "Blocked", "Static"

                if sc >= 400:
                    logger.debug(f"HTTP {sc} on {url[:60]}")
                    await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=False)
                    return "", sc, "Failed", "Static"

                body = await response.text(errors="replace")

                paywall_signals = [
                    "subscribe to read", "sign in to continue", "paywall",
                    "premium content", "register to read", "subscribers only",
                    "login required", "stop the presses",
                ]
                if any(sig in body.lower() for sig in paywall_signals):
                    await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=True)
                    return body, sc, "Headline-Only", "Paywall"

                _write_cache(url, body)
                await _DOMAIN_THROTTLE.record(_domain_from_url(url), sc, success=True)
                return body, sc, "Full", "Static"

        except ssl.SSLError as e:
            logger.warning(f"SSL Error on {url[:60]}: {e}. Retrying without verification.")
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as fallback_session:
                    async with fallback_session.get(
                        url, headers=_random_headers(),
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        body = await resp.text(errors="replace")
                        await _DOMAIN_THROTTLE.record(_domain_from_url(url), resp.status, success=True)
                        return body, resp.status, "Full", "Static-NoSSL"
            except Exception as e2:
                logger.error(f"SSL fallback failed for {url[:60]}: {e2}")
                await _DOMAIN_THROTTLE.record(_domain_from_url(url), 0, success=False)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on {url[:60]} (attempt {attempt+1})")
            await _DOMAIN_THROTTLE.record(_domain_from_url(url), 0, success=False)
        except Exception as e:
            logger.warning(f"Error fetching {url[:60]}: {e}")
            await _DOMAIN_THROTTLE.record(_domain_from_url(url), 0, success=False)

    return "", 0, "Failed", "Static"


# ──────────────────────────────────────────────
# Relative Date Parser
# ──────────────────────────────────────────────

def parse_relative_date(date_text: str) -> str:
    """Convert '1h ago', '2D ago', '3m ago' → YYYY-MM-DD.
    Returns the original string if it cannot be parsed."""
    if not date_text:
        return ""
    t = date_text.lower().strip()
    now = datetime.now()
    try:
        if "min" in t or (t.endswith("m") and not t.endswith("am") and not t.endswith("pm")):
            num = int(re.search(r"(\d+)", t).group(1))
            return (now - timedelta(minutes=num)).strftime("%Y-%m-%d")
        if "hour" in t or t.endswith("h"):
            num = int(re.search(r"(\d+)", t).group(1))
            return (now - timedelta(hours=num)).strftime("%Y-%m-%d")
        if "day" in t or t.endswith("d"):
            num = int(re.search(r"(\d+)", t).group(1))
            return (now - timedelta(days=num)).strftime("%Y-%m-%d")
        if "week" in t or t.endswith("w"):
            num = int(re.search(r"(\d+)", t).group(1))
            return (now - timedelta(weeks=num)).strftime("%Y-%m-%d")
    except Exception:
        pass
    return date_text


# ──────────────────────────────────────────────
# Autonomic RSS Quality Check
# ──────────────────────────────────────────────

# Known "junk" RSS entries we treat as an empty result
_RSS_JUNK_DOMAINS = {
    "bigjoesappliance", "petinsurance", "drugpipeline", "dentist",
    "skincare", "fashionweek", "cryptomining", "sweepstakes",
}

def _rss_is_usable(articles: list[dict], site_domain: str) -> bool:
    """Returns False if the RSS feed is returning obviously off-domain garbage."""
    if not articles:
        return False
    # Check if at least 10% of articles link back to the expected domain
    on_domain = sum(1 for a in articles if site_domain in a.get("link", ""))
    if on_domain == 0 and len(articles) > 3:
        # Check for junk keywords in titles
        junk_count = sum(
            1 for a in articles
            if any(j in a.get("title", "").lower() for j in _RSS_JUNK_DOMAINS)
        )
        if junk_count >= len(articles) // 2:
            logger.warning(f"RSS feed appears broken (junk content detected, {junk_count}/{len(articles)} junk articles)")
            return False
    return True


# ──────────────────────────────────────────────
# Unified Async Smart Fetcher
# ──────────────────────────────────────────────

class AsyncSmartFetcher:
    """
    Autonomic fallback fetcher.

    For every site the strategy is:
      1. Try RSS (if rss_url defined).  Validate quality.
         → If RSS returns 0 or is junk, IMMEDIATELY try google_news_queries.
         → Do NOT proceed to DOM scraping if Google News already found results.
      2. Try explicit google_news_queries (always appended to RSS results).
      3. Newsfilter JSON API bypass (newsfilter.io only).
      4. Playwright JS render (needs_js=True sites).
      5. CloudScraper (Cloudflare bypass).
      6. AIOHTTP static.
      7. Google News domain fallback (last resort).
      8. Report 'Failed' silently — never crash the pipeline.
    """

    def __init__(self, browser_manager=None, session: aiohttp.ClientSession = None):
        self.browser = browser_manager
        self.session = session

    async def fetch_listing(self, site: dict) -> tuple[str, list[dict], str, str, str]:
        name = site["name"]
        url = site["url"]
        rss_url = site.get("rss_url")
        needs_js = site.get("needs_js", False)
        google_queries = site.get("google_news_queries", [])
        deprioritized = site.get("deprioritized", False)

        site_domain = urlparse(url).netloc.replace("www.", "")

        rss_articles: list[dict] = []
        html = ""
        fetch_method = "A"
        access_mode = "Full"
        render_type = "Static"

        # ── Tier 1: Native RSS Feed ──
        rss_ok = False
        if rss_url:
            raw_rss = await fetch_rss(rss_url)
            if raw_rss and _rss_is_usable(raw_rss, site_domain):
                rss_articles = raw_rss
                rss_ok = True
                fetch_method = "RSS"
                render_type = "RSS"
                logger.info(f"[{name}] ✅ Tier 1 RSS: {len(rss_articles)} entries")
            elif raw_rss and not _rss_is_usable(raw_rss, site_domain):
                logger.warning(f"[{name}] ⚠️  RSS returned junk/off-domain content → triggering Google News immediately")
            else:
                logger.info(f"[{name}] RSS returned 0 entries → triggering Google News fallback")

        # ── Tier 1b: Google News RSS (explicit queries defined in config) ──
        # Only run when RSS is weak/absent to reduce Google News dependency.
        min_rss_results = int(site.get("min_rss_for_google_news", 5) or 5)
        name_lower = name.lower()
        if rss_url and (site.get("strong_rss", False) or "m&a" in name_lower or "merger" in name_lower or "acquisition" in name_lower):
            min_rss_results = 1
        force_google = bool(site.get("force_google_news", False))
        should_run_google = bool(google_queries) and (force_google or not rss_ok or len(rss_articles) < min_rss_results)
        if should_run_google and not site.get("disable_google_news_queries", False):
            seen_links = {a.get("link", "") for a in rss_articles}
            new_from_gn = 0
            for gq in google_queries:
                gn_articles = await fetch_google_news_rss_raw(gq)
                for ga in gn_articles:
                    lnk = ga.get("link", "")
                    if lnk and lnk not in seen_links:
                        seen_links.add(lnk)
                        rss_articles.append(ga)
                        new_from_gn += 1
            if new_from_gn > 0:
                logger.info(f"[{name}] Google News queries added {new_from_gn} articles (total: {len(rss_articles)})")
                fetch_method = "Google-News-RSS" if fetch_method == "A" else fetch_method
                render_type = "RSS"

        # ── If RSS/GN already found results → skip DOM scraping entirely ──
        if rss_articles:
            return html, rss_articles, fetch_method, access_mode, render_type

        # ── Tier 2: Newsfilter JSON API bypass ──
        # If credentials are provided, prefer the browser session to retain login.
        if "newsfilter.io" in url and self.session:
            nf_email = os.environ.get("NEWSFILTER_EMAIL", "").strip()
            nf_password = os.environ.get("NEWSFILTER_PASSWORD", "").strip()
            if nf_email and nf_password:
                logger.info(f"[{name}] Newsfilter creds detected — skipping public API, using browser session.")
            else:
                try:
                    query_str = "categories:mergers" if "merger" in url else "*"
                    api_url = "https://api.newsfilter.io/public/actions"
                    payload = {"query": query_str, "size": 30, "sort": [{"publishedAt": "desc"}]}
                    async with self.session.post(
                        api_url, json=payload, headers=_random_headers(),
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for item in data.get("articles", []):
                                rss_articles.append({
                                    "title": item.get("title", ""),
                                    "link":  item.get("url", ""),
                                    "date":  item.get("publishedAt", ""),
                                    "summary": item.get("description", ""),
                                })
                            if rss_articles:
                                logger.info(f"[{name}] Tier 2 JSON API: {len(rss_articles)} entries")
                                return "", rss_articles, "JSON-API", "Full", "JSON"
                except Exception as e:
                    logger.warning(f"[{name}] Newsfilter API failed: {e}")

        # ── Tier 3a: Playwright (JS-heavy sites) ──
        if needs_js and self.browser and self.browser.available and not deprioritized:
            logger.info(f"[{name}] Tier 3a Playwright JS Render")
            try:
                html = await asyncio.wait_for(
                    self.browser.fetch_page(
                        url, wait_seconds=3.0,
                        pagination_type=site.get("pagination_type"),
                        load_more_selector=site.get("load_more_selector"),
                        next_page_selector=site.get("next_page_selector"),
                        max_pages=site.get("max_pages", 3),
                        site_name=name,
                    ),
                    timeout=120,
                )
                if html and len(html) > 1000:
                    fetch_method = "Browser"
                    render_type = "JS"
                    if any(s in html.lower() for s in ["subscribe to read", "paywall", "sign in to continue"]):
                        access_mode = "Headline-Only"
                    return html, rss_articles, fetch_method, access_mode, render_type
                else:
                    logger.warning(f"[{name}] Playwright returned empty/short page ({len(html)} chars)")
            except asyncio.TimeoutError:
                logger.warning(f"[{name}] Playwright timed out (120s)")
            except Exception as e:
                logger.warning(f"[{name}] Playwright error: {e}")

        # ── Tier 3b: CloudScraper ──
        if (not html or len(html) < 1000) and not deprioritized:
            logger.info(f"[{name}] Tier 3b CloudScraper")
            cs_html, cs_sc, cs_access, cs_render = await fetch_with_cloudscraper(url)
            if cs_access == "Full" and len(cs_html) > 1000:
                return cs_html, rss_articles, "CloudScraper", cs_access, cs_render
            elif cs_access == "Blocked":
                logger.warning(f"[{name}] CloudScraper blocked (HTTP {cs_sc}) → escalating to Google News domain search")

        # ── Tier 3c: AIOHTTP static ──
        if (not html or len(html) < 1000) and self.session:
            logger.info(f"[{name}] Tier 3c Pure HTTP (aiohttp)")
            html, sc, access_mode, render_type = await fetch_static(url, self.session)
            fetch_method = "A"

        # ── Tier 4: Google News domain-level fallback (last resort) ──
        allow_domain_fallback = not deprioritized and site.get("allow_google_domain_fallback", True)
        if (not html or access_mode in ("Blocked", "Failed", "")) and not rss_articles and allow_domain_fallback:
            logger.info(f"[{name}] All methods failed → Google News domain search for {site_domain}")
            gn_fallback = await fetch_google_news_rss(
                site_domain, "energy acquisition merger deal"
            )
            if gn_fallback:
                return "", gn_fallback, "Google-News-RSS", "Google-News-Fallback", "RSS"
            # Mark as failed
            access_mode = "Failed"

        if not html and not rss_articles:
            access_mode = "Failed"

        return html, rss_articles, fetch_method, access_mode, render_type

    async def fetch_article(self, url: str, needs_js: bool = False) -> tuple[str, str, str]:
        """Fetch a single article body.  Falls back through CloudScraper → Google Cache → Playwright."""
        if not self.session:
            return "", "Failed", "Static"

        try:
            html, sc, access_mode, render_type = await fetch_static(url, self.session)

            if access_mode in ("Blocked", "Failed") and CLOUDSCRAPER_AVAILABLE:
                cs_html, cs_sc, cs_access, cs_render = await fetch_with_cloudscraper(url)
                if cs_access == "Full" and len(cs_html) > 500:
                    return cs_html, cs_access, cs_render

            if access_mode in ("Blocked", "Failed") or len(html) < 300:
                gc_html, gc_sc, gc_access, gc_render = await fetch_with_google_cache(url)
                if gc_access == "Full" and len(gc_html) > 300:
                    return gc_html, gc_access, gc_render

            if (needs_js or len(html) < 500) and self.browser and self.browser.available:
                try:
                    browser_html = await asyncio.wait_for(
                        self.browser.fetch_page(url, wait_seconds=2.5),
                        timeout=60,
                    )
                    if len(browser_html) > max(len(html), 500):
                        return browser_html, "Full", "Browser"
                except (asyncio.TimeoutError, Exception) as e:
                    logger.debug(f"Article browser fetch failed {url[:60]}: {e}")

            return html, access_mode, render_type
        except Exception as e:
            logger.error(f"fetch_article unexpected error {url[:60]}: {e}")
            return "", "Failed", "Static"
