"""
extractor.py — M&A Deal extraction, confidence scoring, and entity recognition.

Key improvement: Buyer/Seller extraction now uses multiple headline-centric
regex patterns that match the most common M&A headline formats.
"""

import re
import json
import logging
from bs4 import BeautifulSoup
from readability import Document

try:
    from .config import RE_STRONG, RE_MEDIUM, RE_OTHER, determine_industry_and_sector
    from .ai_extractor import AsyncAIExtractor
except ImportError:
    from config import RE_STRONG, RE_MEDIUM, RE_OTHER, determine_industry_and_sector
    from ai_extractor import AsyncAIExtractor

logger = logging.getLogger("energy_scraper.extractor")

# Trafilatura: recommended by the scraping community for highest boilerplate-removal accuracy.
# Falls back to readability then BeautifulSoup if unavailable.
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.info("trafilatura not installed — using readability fallback")

# Wire PR / Press-Release boilerplate section delimiters
# Everything after these markers is noise for entity extraction
_PR_BOILERPLATE_MARKERS = [
    r"about [a-z\s&,]{3,60}\n",          # About Company Name
    r"about the company",
    r"about us\b",
    r"forward.looking statements?",
    r"safe harbor",
    r"non-gaap",
    r"cautionary (note|statement)",
    r"investor relations contact",
    r"media contact[s]?",
    r"for (more |further )?information[,:]?",
    r"for immediate release",
    r"source:",
    r"\*\*\*",
    r"###",                              # Standard PR end-of-release marker
]
_PR_BOILERPLATE_RE = re.compile(
    "|".join(_PR_BOILERPLATE_MARKERS), re.IGNORECASE | re.MULTILINE
)


class DealExtractor:

    def __init__(self):
        self.ai = AsyncAIExtractor()
        
        # Headline-centric M&A extraction patterns
        self._ACQUISITION_PATTERNS = [
            r"(.+?)\s+completes(?: its)? acquisition of\s+(.+)",
            r"(.+?)\s+closes(?: its)? acquisition of\s+(.+)",
            r"(.+?)\s+to acquire\s+(.+)",
            r"(.+?)\s+acquires\s+(.+)",
            r"(.+?)\s+to buy\s+(.+)",
            r"(.+?)\s+buys\s+(.+)",
            r"(.+?)\s+agrees to acquire\s+(.+)",
            r"(.+?)\s+agrees to buy\s+(.+)",
            r"acquisition of\s+(.+?)\s+by\s+(.+)",
        ]

        self._STAKE_PATTERNS = [
            r"(.+?)\s+acquires\s+(?:a |an )?(?:\d+% )?stake in\s+(.+)",
            r"(.+?)\s+to acquire\s+(?:a |an )?(?:\d+% )?stake in\s+(.+)",
            r"(.+?)\s+buys\s+(?:a |an )?(?:\d+% )?stake in\s+(.+)",
        ]

        self._DIVESTITURE_PATTERNS = [
            r"(.+?)\s+to sell\s+(.+)",
            r"(.+?)\s+sells\s+(.+)",
            r"(.+?)\s+to divest\s+(.+)",
            r"(.+?)\s+divests\s+(.+)",
            r"(.+?)\s+completes sale of\s+(.+)",
        ]

        self._JV_PATTERNS = [
            r"(.+?)\s+and\s+(.+?)\s+form(?: a)? joint venture",
            r"(.+?)\s+and\s+(.+?)\s+to form(?: a)? joint venture",
        ]

    def clean_html(self, html_content: str) -> str:
        """Extract clean article text from HTML.

        Priority:
          1. trafilatura  — best boilerplate removal, benchmark leader
          2. readability  — good for article-style pages
          3. BeautifulSoup fallback
        """
        if not html_content:
            return ""

        # Tier 1: trafilatura (recommended by webscraping community, highest precision)
        if TRAFILATURA_AVAILABLE:
            try:
                result = trafilatura.extract(
                    html_content,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False,
                    favor_precision=True,
                )
                if result and len(result.strip()) > 100:
                    return re.sub(r"\s+", " ", result).strip()
            except Exception as e:
                logger.debug(f"trafilatura failed: {e}")

        # Tier 2: readability-lxml
        try:
            doc = Document(html_content)
            distilled_html = doc.summary()
            soup = BeautifulSoup(distilled_html, "html.parser")
        except Exception as e:
            logger.debug(f"Readability failed, falling back to soup: {e}")
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.extract()

        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _clean_pr_body(text: str) -> str:
        """Strip wire-PR boilerplate from article body text.

        Finds the first boilerplate marker (About, Safe Harbor, Contact, ###, etc.)
        and truncates everything after it.  This prevents IndexBox/BusinessWire
        PR footers from polluting the AI entity extraction.

        Returns the cleaned text (minimum 100 chars required, else returns original).
        """
        if not text or len(text) < 200:
            return text

        m = _PR_BOILERPLATE_RE.search(text)
        if m and m.start() > 150:  # Only truncate if there is meaningful content before the marker
            cleaned = text[:m.start()].strip()
            if len(cleaned) >= 100:
                logger.debug(f"PR body cleaner: truncated {len(text)} -> {len(cleaned)} chars")
                return cleaned

        return text


    # ── Article metadata extraction ──

    def extract_article_metadata(self, html_content: str) -> tuple:
        """Returns (headline, date_str, body_text)."""
        if not html_content:
            return "", "", ""

        soup = BeautifulSoup(html_content, "html.parser")

        headline = ""
        h1 = soup.find("h1")
        if h1:
            headline = h1.get_text(strip=True)
        else:
            title = soup.find("title")
            headline = title.get_text(strip=True) if title else ""

        date_str = ""
        date_meta_names = [
            ("property", "article:published_time"),
            ("property", "og:article:published_time"),
            ("name", "pubdate"),
            ("name", "date"),
            ("name", "DC.date.issued"),
            ("itemprop", "datePublished"),
            ("name", "sailthru.date"),
            ("name", "article.published"),
        ]
        for attr, val in date_meta_names:
            m = soup.find("meta", {attr: val})
            if m and m.get("content"):
                date_str = m["content"]
                break

        if not date_str:
            time_tag = soup.find("time")
            if time_tag:
                date_str = time_tag.get("datetime", time_tag.get_text(strip=True))

        if not date_str:
            ds = soup.find("span", class_=re.compile(r"date|pubdate|published|timestamp", re.I))
            if ds:
                date_str = ds.get_text(strip=True)

        if not date_str:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict):
                        date_str = data.get("datePublished", data.get("dateCreated", ""))
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                date_str = item.get("datePublished", "")
                                if date_str:
                                    break
                except Exception:
                    pass
                if date_str:
                    break

        body_text = self.clean_html(html_content)
        # Apply PR boilerplate cleaner BEFORE handing text to AI
        body_text = self._clean_pr_body(body_text)
        return headline, date_str, body_text

    # ── Confidence scoring ──

    def compute_confidence(self, headline: str, full_text: str, is_paywalled: bool = False) -> float:
        combined = (headline + " " + full_text).lower()

        strong = len(RE_STRONG.findall(combined))
        medium = len(RE_MEDIUM.findall(combined))
        other  = len(RE_OTHER.findall(combined))

        h_strong = len(RE_STRONG.findall(headline.lower()))
        h_medium = len(RE_MEDIUM.findall(headline.lower()))
        h_other  = len(RE_OTHER.findall(headline.lower()))

        score = 0.0

        if strong >= 3:
            score = 0.95
        elif strong >= 2:
            score = 0.90
        elif strong == 1 and medium >= 1:
            score = 0.85
        elif strong == 1:
            score = 0.75
        elif medium >= 2:
            score = 0.70
        elif medium == 1 and other >= 2:
            score = 0.60
        elif medium == 1:
            score = 0.50
        elif other >= 3:
            score = 0.45
        elif other >= 2:
            score = 0.38
        elif other == 1:
            score = 0.25

        if h_strong >= 1:
            score = max(score, 0.80)
        elif h_medium >= 1:
            score = max(score, 0.60)

        if is_paywalled:
            if h_strong > 0 or h_medium > 0:
                score = max(score, 0.60)
            elif other > 0:
                score = max(score, 0.40)

        # ── Review Queue Routing: "Exploring a Merger" / Rumors -> Max 0.50 ──
        if h_other >= 1 or other >= 3:
            # If headline contains "considers", "explores", "weighs", cap at exactly 0.50
            # so it goes to Review Queue instead of being an auto-deal.
            score = min(score, 0.50)

        return min(score, 1.0)

    # ── Industry classification ──

    def determine_industry(self, text: str) -> tuple:
        return determine_industry_and_sector(text)

    # ── Entity extraction (IMPROVED) ──

    # Pre-compiled entity name pattern: starts with uppercase, allows multi-word
    # company names like "TotalEnergies SE", "3D Oil", "PBF Energy Inc."
    _ENTITY = r"([A-Z0-9][\w\s&'.,()/-]{2,80}?)"

    # Buyer/Seller headline patterns — ordered from most specific to generic
    _ACQUISITION_PATTERNS = [
        # "X to acquire Y" / "X acquires Y" / "X has acquired Y"
        rf"{_ENTITY}\s+(?:to acquire|acquires?|has acquired|will acquire)\s+{_ENTITY}",
        # "X completes/finalizes/closes acquisition of Y"
        rf"{_ENTITY}\s+(?:completes?|finalizes?|closes?)\s+(?:the\s+)?acquisition\s+of\s+{_ENTITY}",
        # "X to buy Y" / "X buys Y"
        rf"{_ENTITY}\s+(?:to buy|buys?|to purchase|purchases?|has purchased|has bought)\s+{_ENTITY}",
        # "X to merge with Y"
        rf"{_ENTITY}\s+(?:to merge|merges?|agrees? to merge)\s+with\s+{_ENTITY}",
        # "X announces acquisition of Y"
        rf"{_ENTITY}\s+(?:announces?|reveals?|proposes?)\s+(?:the\s+)?acquisition\s+of\s+{_ENTITY}",
        # "X enters into agreement to acquire Y"
        rf"{_ENTITY}\s+(?:enters?\s+(?:into\s+)?(?:an?\s+)?(?:agreement|deal)\s+to\s+(?:acquire|buy|purchase))\s+{_ENTITY}",
        # "Acquisition of Y by X" (reversed)
        r"[Aa]cquisition\s+of\s+" + _ENTITY + r"\s+by\s+" + _ENTITY,
    ]

    _DIVESTITURE_PATTERNS = [
        # "X sells Y" / "X to sell Y" / "X divests Y"
        rf"{_ENTITY}\s+(?:sells?|to sell|divests?|to divest|has sold|disposes?\s+of)\s+{_ENTITY}",
        # "X completes sale of Y"
        rf"{_ENTITY}\s+(?:completes?|finalizes?|closes?)\s+(?:the\s+)?(?:sale|divestiture|disposal)\s+of\s+{_ENTITY}",
    ]

    _JV_PATTERNS = [
        # "X and Y form/enter/sign/announce joint venture"
        rf"{_ENTITY}\s+and\s+{_ENTITY}\s+(?:form|enter|sign|announce|create|establish|launch)",
        # "X and Y to develop / partner on"
        rf"{_ENTITY}\s+and\s+{_ENTITY}\s+(?:to develop|partner|collaborate|team up)",
    ]

    _STAKE_PATTERNS = [
        # "X acquires N% stake in Y"
        rf"{_ENTITY}\s+(?:acquires?|buys?|purchases?|takes?)\s+\d+%?\s+(?:stake|interest|share)\s+in\s+{_ENTITY}",
        # "X to take N% stake in Y"
        rf"{_ENTITY}\s+(?:to take|to acquire|takes?)\s+(?:a\s+)?\d+%?\s+(?:stake|interest)\s+in\s+{_ENTITY}",
    ]

    async def extract_deal_entities(self, headline: str, body_text: str) -> dict:
        """
        Extract enriched deal entities using ARIA-powered AI extraction.
        Returns a dict with: buyer, seller, asset, value, geography, deal_type, deal_status, strategic_rationale.
        """
        # ── AI Extraction (Primary) ──
        if self.ai.enabled:
            allow_ai = True
            if getattr(self.ai, "budget_mode", False):
                combined = (headline + " " + body_text).lower()
                if not (RE_STRONG.search(combined) or RE_MEDIUM.search(combined)):
                    allow_ai = False
            if allow_ai:
                ai_data = await self.ai.extract_deal(headline, body_text)
                if ai_data:
                    # ai_data already contains buyer, seller, asset, value, industry, sector,
                    # deal_type, deal_status, geography, strategic_rationale
                    return ai_data
        
        # ── Regex Fallback ──
        buyer  = "Unknown"
        seller = "Unknown"
        asset  = headline[:150] if headline else "Unknown"
        value  = "Undisclosed"
        geography = "Global"
        deal_type = "M&A"
        deal_status = "Announced"
        rationale = "No rationale provided (Regex extraction)"
        
        search_text = headline  # Try headline first

        # ── Buyer / Seller from acquisition patterns ──
        for pat in self._ACQUISITION_PATTERNS:
            m = re.search(pat, search_text)
            if m:
                if "by" in pat.lower() and "acquisition of" in pat.lower():
                    # Reversed pattern: "Acquisition of Y by X"
                    seller = self._clean_entity(m.group(1))
                    buyer  = self._clean_entity(m.group(2))
                else:
                    buyer  = self._clean_entity(m.group(1))
                    seller = self._clean_entity(m.group(2))
                break

        # ── Stake patterns ──
        if buyer == "Unknown":
            for pat in self._STAKE_PATTERNS:
                m = re.search(pat, search_text)
                if m:
                    buyer  = self._clean_entity(m.group(1))
                    seller = self._clean_entity(m.group(2))
                    break

        # ── Divestiture patterns ── (seller is group 1)
        if buyer == "Unknown" and seller == "Unknown":
            for pat in self._DIVESTITURE_PATTERNS:
                m = re.search(pat, search_text)
                if m:
                    seller = self._clean_entity(m.group(1))
                    asset  = self._clean_entity(m.group(2))
                    break

        # ── JV patterns ──
        if buyer == "Unknown" and seller == "Unknown":
            for pat in self._JV_PATTERNS:
                m = re.search(pat, search_text)
                if m:
                    buyer  = self._clean_entity(m.group(1))
                    seller = self._clean_entity(m.group(2))
                    break

        # ── Fallback: try the same patterns on first 500 chars of body ──
        if buyer == "Unknown" and seller == "Unknown" and body_text:
            body_snippet = body_text[:500]
            for pat in self._ACQUISITION_PATTERNS + self._STAKE_PATTERNS:
                m = re.search(pat, body_snippet)
                if m:
                    buyer  = self._clean_entity(m.group(1))
                    seller = self._clean_entity(m.group(2))
                    break

        # ── Value extraction ──
        value_patterns = [
            r"\$\s*[\d,.]+\s*(?:billion|million|bn|mn|m|b|trillion|tn)",
            r"(?:USD|EUR|GBP|CAD|AUD)\s*[\d,.]+\s*(?:billion|million|bn|mn|m|b)?",
            r"[\d,.]+\s*(?:billion|million|trillion)\s*(?:dollars|euros|pounds)",
            r"(?:worth|valued at|deal value|transaction value|for)\s+\$\s*[\d,.]+\s*(?:billion|million|bn|mn)?",
        ]
        combined_val = headline + " " + (body_text[:3000] if body_text else "")
        for vp in value_patterns:
            vm = re.search(vp, combined_val, re.IGNORECASE)
            if vm:
                value = vm.group(0).strip()
                break

        # ── Country / Region (Geography) ──
        countries = [
            "United States", "USA", "U.S.", "Canada", "UK", "United Kingdom",
            "Australia", "Brazil", "India", "Norway", "Germany", "France",
            "Mexico", "Nigeria", "Angola", "Saudi Arabia", "UAE", "Qatar",
            "China", "Japan", "South Korea", "Indonesia", "Egypt", "Libya",
            "South Africa", "Colombia", "Argentina", "Chile", "Peru", "Ghana",
            "Kenya", "Mozambique", "Tanzania", "Guyana", "Suriname", "Trinidad",
            "Italy", "Spain", "Netherlands", "Poland", "Romania", "Turkey",
            "Israel", "Kazakhstan", "Malaysia", "Vietnam", "Philippines",
            "Thailand", "New Zealand", "Ireland", "Denmark", "Sweden",
            "Finland", "Belgium", "Austria", "Switzerland", "Oman",
            "Kuwait", "Bahrain", "Iraq", "Russia", "Namibia",
            "Papua New Guinea", "Pakistan", "Morocco", "Algeria",
            "Sicily", "Texas", "North Sea", "Gulf of Mexico",
            "Permian Basin", "Appalachia", "Bakken", "Eagle Ford",
            "Haynesville", "Marcellus", "Oklahoma", "Colorado",
            "New Mexico", "Wyoming", "Louisiana", "Alaska",
            "Alberta", "British Columbia", "Western Australia",
            "Scotland", "Aberdeen", "Stavanger",
        ]
        combined_geo = headline + " " + (body_text[:2000] if body_text else "")
        for c in countries:
            if c.lower() in combined_geo.lower():
                geography = c
                break

        return {
            "buyer": buyer,
            "seller": seller,
            "asset": asset,
            "value": value,
            "geography": geography,
            "deal_type": deal_type,
            "deal_status": deal_status,
            "strategic_rationale": rationale
        }

    @staticmethod
    def _clean_entity(raw: str) -> str:
        """Clean up captured entity name."""
        if not raw:
            return "Unknown"
        name = raw.strip().rstrip(".,;:- ")
        # Remove trailing filler words
        for suffix in [" to", " has", " will", " its", " the", " a", " an",
                       " for", " in", " of", " with", " and"]:
            if name.lower().endswith(suffix):
                name = name[:len(name)-len(suffix)].strip()
        # Truncate if too long
        if len(name) > 80:
            name = name[:80].rsplit(" ", 1)[0]
        return name if len(name) > 1 else "Unknown"

    # ── Full article processing pipeline ──

    async def process_article(self, html_content, url, extracted_date=None, is_paywalled=False):
        headline, date_str, body_text = self.extract_article_metadata(html_content)
        final_date = extracted_date or date_str
        confidence = self.compute_confidence(headline, body_text, is_paywalled)
        industry, sector = determine_industry_and_sector(headline + " " + body_text)
        
        entities = await self.extract_deal_entities(headline, body_text)

        return {
            "Headline": headline,
            "Buyer": entities["buyer"],
            "Seller": entities["seller"],
            "Asset": entities["asset"],
            "Date": final_date,
            "Industry": industry,
            "Sector": sector,
            "Link": url,
            "Geography": entities["geography"],
            "Value": entities["value"],
            "Deal Type": entities["deal_type"],
            "Deal Status": entities["deal_status"],
            "Strategic Rationale": entities["strategic_rationale"],
            "Confidence": confidence,
        }
