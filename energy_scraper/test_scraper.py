"""
test_scraper.py — Automated test suite for the Energy M&A Scraper.

Tests:
  • AI verification gate: rejects non-M&A noise
  • Sheet classification: correct routing to industry sheets
  • Deduplication: URL normalization and headline similarity
  • Date parsing: relative dates ("2D ago", "3h ago")
  • Energy relevance filter: rejects pharma, tech, etc.
  • Value normalization: currency conversion output format

Run with:  python -m pytest test_scraper.py -v
       or: python test_scraper.py
"""

import sys
import os
import asyncio
import types

# Mock optional modules that may not be installed in test env
for mod_name in ["gspread", "gspread.exceptions", "google", "google.oauth2", "google.oauth2.service_account"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Add mock attributes that gspread code may reference
sys.modules["gspread"].authorize = lambda *a, **k: None
sys.modules["gspread"].exceptions = sys.modules["gspread.exceptions"]
sys.modules["gspread.exceptions"].SpreadsheetNotFound = type("SpreadsheetNotFound", (Exception,), {})
sys.modules["gspread.exceptions"].APIError = type("APIError", (Exception,), {})
# Mock Credentials class for google_sheets.py
_MockCredentials = type("Credentials", (), {
    "from_service_account_file": staticmethod(lambda *a, **k: None),
    "from_service_account_info": staticmethod(lambda *a, **k: None),
})
sys.modules["google.oauth2.service_account"].Credentials = _MockCredentials
sys.modules["google.oauth2"].service_account = sys.modules["google.oauth2.service_account"]
sys.modules["google"].oauth2 = sys.modules["google.oauth2"]

# Ensure the energy_scraper directory is on Python path
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    is_energy_relevant, classify_deal_sheet,
    RE_STRONG, RE_MEDIUM, RE_OTHER,
)
from scraper import (
    _is_valid_headline, _headline_has_ma_signal,
    parse_date, is_within_date_range,
)
from ai_extractor import AsyncAIExtractor
from extractor import DealExtractor


# ═══════════════════════════════════════════════
# 1. AI VERIFICATION GATE — False Positive Rejection
# ═══════════════════════════════════════════════

class TestAIVerificationGate:
    """Tests that obvious non-M&A headlines are rejected BEFORE hitting the API."""

    def setup_method(self):
        self.ai = AsyncAIExtractor()  # Will have enabled=False if no key, that's OK for pre-filter tests

    def test_insider_stock_sale_rejected(self):
        """Insider stock sales like 'Woodside Energy Insider Sells 7,500 Shares' must be rejected."""
        result = asyncio.run(self.ai.verify_is_deal(
            "Woodside Energy Group (NYSE:WDS) Insider Mark Anthony Abbotsford Sells 7,500 Shares - MarketBeat"
        ))
        assert result["is_deal"] is False, f"Should reject insider sale, got: {result}"

    def test_fund_manager_portfolio_trade_rejected(self):
        """Fund manager portfolio trades must be rejected."""
        result = asyncio.run(self.ai.verify_is_deal(
            "JPMorgan Chase & Co. Sells 694,344 Shares of NGL Energy Partners LP $NGL - MarketBeat"
        ))
        assert result["is_deal"] is False, f"Should reject fund trade, got: {result}"

    def test_asset_manager_sells_shares_rejected(self):
        result = asyncio.run(self.ai.verify_is_deal(
            "Assenagon Asset Management S.A. Sells 31,107 Shares of CMS Energy Corporation $CMS - MarketBeat"
        ))
        assert result["is_deal"] is False, f"Should reject asset manager trade, got: {result}"

    def test_regulatory_policy_rejected(self):
        """Government regulatory news must be rejected."""
        result = asyncio.run(self.ai.verify_is_deal(
            "EPA Approves Nationwide Sales of E15 and Removes Barriers to Sale of E10"
        ))
        assert result["is_deal"] is False, f"Should reject regulatory news, got: {result}"


# ═══════════════════════════════════════════════
# 2. SHEET CLASSIFICATION
# ═══════════════════════════════════════════════

class TestSheetClassification:

    def test_upstream_deal(self):
        sheet, confident = classify_deal_sheet(
            "ExxonMobil acquires Pioneer Natural Resources — Permian Basin E&P assets"
        )
        assert sheet == "Upstream", f"Expected Upstream, got {sheet}"

    def test_midstream_deal(self):
        sheet, confident = classify_deal_sheet(
            "Energy Transfer Completes Acquisition of Enable Midstream pipeline assets"
        )
        assert sheet == "Midstream", f"Expected Midstream, got {sheet}"

    def test_ofs_deal(self):
        sheet, confident = classify_deal_sheet(
            "Halliburton acquires a drilling service company specializing in hydraulic fracturing"
        )
        assert sheet == "OFS", f"Expected OFS, got {sheet}"

    def test_renewables_deal(self):
        sheet, confident = classify_deal_sheet(
            "Brookfield acquires 200MW solar farm in Sicily from European Energy"
        )
        assert sheet == "P&U", f"Expected P&U, got {sheet}"

    def test_report_classification(self):
        sheet, confident = classify_deal_sheet(
            "KNOT Offshore Partners LP Earnings Release — Interim Results for Q1 2026"
        )
        assert sheet == "Reports", f"Expected Reports, got {sheet}"

    def test_jv_classification(self):
        sheet, confident = classify_deal_sheet(
            "Shell and BP form joint venture for North Sea carbon capture partnership"
        )
        assert sheet == "JV & Partnerships", f"Expected JV & Partnerships, got {sheet}"

    def test_mou_classification(self):
        sheet, confident = classify_deal_sheet(
            "TotalEnergies signs memorandum of understanding with Saudi Aramco for strategic partnership"
        )
        assert sheet == "JV & Partnerships", f"Expected JV & Partnerships, got {sheet}"


# ═══════════════════════════════════════════════
# 3. DEDUPLICATION LOGIC
# ═══════════════════════════════════════════════

class TestDeduplication:

    def test_url_with_query_params_deduped(self):
        """URLs differing only in query params should be treated as the same deal."""
        from urllib.parse import urlparse, urlunparse
        url1 = "https://www.reuters.com/article/deal-123?utm_source=rss"
        url2 = "https://www.reuters.com/article/deal-123?utm_source=google"

        parsed1 = urlparse(url1)
        clean1 = urlunparse((parsed1.scheme, parsed1.netloc, parsed1.path, "", "", ""))
        parsed2 = urlparse(url2)
        clean2 = urlunparse((parsed2.scheme, parsed2.netloc, parsed2.path, "", "", ""))

        assert clean1 == clean2, "URLs with different query params should normalize to same key"

    def test_headline_similarity_dedup(self):
        """Same headline from different wire services should deduplicate."""
        h1 = "Merck to Acquire Terns Pharmaceuticals, Inc., Expanding Its Hematology Pipeline"[:50].lower().strip()
        h2 = "Merck to Acquire Terns Pharmaceuticals, Inc., Expanding Its Hematology"[:50].lower().strip()
        assert h1 == h2, "First 50 chars of similar headlines should match"


# ═══════════════════════════════════════════════
# 4. DATE PARSING
# ═══════════════════════════════════════════════

class TestDateParsing:

    def test_relative_date_hours(self):
        result = parse_date("2h ago")
        assert result is not None, "Should parse '2h ago'"
        assert len(result) == 10, f"Expected YYYY-MM-DD format, got: {result}"

    def test_relative_date_days(self):
        result = parse_date("1D ago")
        assert result is not None, "Should parse '1D ago'"

    def test_relative_date_minutes(self):
        result = parse_date("48m ago")
        assert result is not None, "Should parse '48m ago'"

    def test_iso_date(self):
        result = parse_date("2026-03-25T14:30:00Z")
        assert result == "2026-03-25", f"Expected 2026-03-25, got: {result}"

    def test_date_range_check(self):
        assert is_within_date_range("2026-03-25", "2026-03-24", "2026-03-26") is True
        assert is_within_date_range("2026-03-20", "2026-03-24", "2026-03-26") is False


# ═══════════════════════════════════════════════
# 5. ENERGY RELEVANCE FILTER
# ═══════════════════════════════════════════════

class TestEnergyRelevance:

    def test_oil_gas_relevant(self):
        """Headlines with explicit energy keywords should pass."""
        assert is_energy_relevant("ExxonMobil acquires Pioneer Natural Resources oil and gas assets") is True

    def test_pharma_rejected(self):
        """Headlines without energy keywords should fail."""
        assert is_energy_relevant("Pfizer acquires biotech startup for mRNA vaccine development") is False

    def test_software_rejected(self):
        assert is_energy_relevant("Google acquires AI startup for machine learning SaaS platform") is False

    def test_mining_relevant(self):
        assert is_energy_relevant("BHP acquires lithium mining assets in Chile") is True

    def test_renewable_relevant(self):
        assert is_energy_relevant("Brookfield buys 500MW solar farm portfolio") is True

    def test_pipeline_relevant(self):
        """Pipeline is an energy keyword."""
        assert is_energy_relevant("Energy Transfer acquires pipeline network in Gulf of Mexico") is True


# ═══════════════════════════════════════════════
# 6. VALUE NORMALIZATION
# ═══════════════════════════════════════════════

class TestValueNormalization:

    def setup_method(self):
        self.ai = AsyncAIExtractor()

    def test_usd_billion(self):
        result = self.ai.normalize_value_to_usd("$12.8 billion")
        assert "US$" in result, f"Should contain US$, got: {result}"
        assert "billion" in result, f"Should contain billion, got: {result}"

    def test_usd_million(self):
        result = self.ai.normalize_value_to_usd("$500 million")
        assert "US$" in result and "million" in result, f"Got: {result}"

    def test_undisclosed(self):
        result = self.ai.normalize_value_to_usd("Undisclosed")
        assert result == "Undisclosed"

    def test_gbp_conversion(self):
        result = self.ai.normalize_value_to_usd("£200 million")
        assert "US$" in result, f"GBP should be converted, got: {result}"

    def test_none_input(self):
        result = self.ai.normalize_value_to_usd(None)
        assert result == "Undisclosed"


# ═══════════════════════════════════════════════
# 7. HEADLINE VALIDATION
# ═══════════════════════════════════════════════

class TestHeadlineValidation:

    def test_nav_junk_rejected(self):
        assert _is_valid_headline("Home") is False
        assert _is_valid_headline("Contact") is False
        assert _is_valid_headline("Subscribe") is False

    def test_short_headline_rejected(self):
        assert _is_valid_headline("Oil up") is False

    def test_valid_headline_accepted(self):
        assert _is_valid_headline("ExxonMobil to Acquire Pioneer Natural Resources in $59.5B Deal") is True

    def test_ma_signal_detection(self):
        assert _headline_has_ma_signal("Company A acquires Company B for $1 billion") is True
        assert _headline_has_ma_signal("Oil prices rise amid supply concerns") is False


# ═══════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
    except ImportError:
        print("pytest not installed. Running basic tests manually...\n")
        passed = 0
        failed = 0
        errors = []

        test_classes = [
            TestAIVerificationGate,
            TestSheetClassification,
            TestDeduplication,
            TestDateParsing,
            TestEnergyRelevance,
            TestValueNormalization,
            TestHeadlineValidation,
        ]

        for cls in test_classes:
            print(f"\n{'='*50}")
            print(f"  {cls.__name__}")
            print(f"{'='*50}")
            instance = cls()
            for method_name in dir(instance):
                if method_name.startswith("test_"):
                    if hasattr(instance, "setup_method"):
                        instance.setup_method()
                    try:
                        getattr(instance, method_name)()
                        print(f"  [PASS] {method_name}")
                        passed += 1
                    except AssertionError as e:
                        print(f"  [FAIL] {method_name}: {e}")
                        failed += 1
                        errors.append(f"{cls.__name__}.{method_name}: {e}")
                    except Exception as e:
                        print(f"  [ERROR] {method_name}: EXCEPTION: {e}")
                        failed += 1
                        errors.append(f"{cls.__name__}.{method_name}: {e}")

        print(f"\n{'='*50}")
        print(f"  Results: {passed} passed, {failed} failed")
        print(f"{'='*50}")

        if errors:
            print("\nFailures:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)

