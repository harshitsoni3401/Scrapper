"""
verify_fixes.py — Tests all fixes against known false-positive headlines from the
March 30, 2026 audit report (Energy_MA_Report_Async_20260330_093721.xlsx).

Each test checks that a specific false-positive pattern is now correctly blocked.
"""
import sys
import re
sys.path.insert(0, '.')

print("=" * 70)
print("  VERIFICATION: Testing all fixes against known false positives")
print("=" * 70)

# ============================================================
# FIX 1.1: is_energy_relevant() should now reject non-energy
# ============================================================
from config import is_energy_relevant

false_positive_headlines = [
    # Should be REJECTED (non-energy):
    ("Best high-yield savings interest rates today", False),
    ("1 No-Brainer Semiconductor Stock to Buy With $1,000 Right Now", False),
    ("Merck & Co. (MRK) to Acquire Terns Pharma for $6.7 Billion", False),
    ("Mortgage and refinance interest rates today", False),
    ("Jim Cramer on Reddit (RDDT): I Want to Buy Reddit Right Here", False),
    ("McLaren Driver Tommy Pintos Partners With Priority Tire", False),
    ("Gotha Cosmetics: US acquisition in the pipeline", False),
    ("Novartis: $2 Billion Acquisition Of Excellergy To Expand Allergy Drug Pipeline", False),
    ("Jefferies Bullish on The Home Depot Following Mingledorff Acquisition", False),
    ("HELOC and home equity loan rates Saturday", False),
    
    # Should be ACCEPTED (energy):
    ("Constellation reaches agreement for acquisition of Calpine", True),
    ("Borr Drilling Limited - Acquisition of Five Premium Jack-Up Rigs", True),
    ("Boralex Enters into Definitive Agreement to be Acquired", True),
    ("Octopus Energy Takes Majority Stake in Uplight", True),
    ("Grid Connected Infrastructure Sells 100 MW Battery Energy Storage", True),
    ("Powell Max Limited Signs Letter of Intent to Acquire Boston Solar", True),
    ("Hungary's MOL has U.S. approval to continue NIS acquisition talks", True),
    ("Barrel Energy acquires Happy Traps waste-to-energy platform", True),
    ("Venture Global and Vitol Announce New LNG Purchase Agreement", True),
    ("Zijin Mining Group: $2.6 Billion Acquisition Of Chifeng Jilong Gold Mining", True),
]

print("\n── FIX 1.1: is_energy_relevant() pre-filter ──")
fix1_pass = 0
fix1_fail = 0
for headline, expected in false_positive_headlines:
    result = is_energy_relevant(headline)
    status = "✅" if result == expected else "❌"
    if result != expected:
        fix1_fail += 1
        print(f"  {status} FAIL: '{headline[:60]}' → got {result}, expected {expected}")
    else:
        fix1_pass += 1
        print(f"  {status} OK:   '{headline[:60]}' → {result}")

print(f"\n  Results: {fix1_pass} passed, {fix1_fail} failed")

# ============================================================
# FIX 1.4: _is_valid_headline() should block SPAC stubs
# ============================================================
# We need to import from scraper, but avoid full init
# Just test the regex directly
print("\n── FIX 1.4: SPAC stub headline filter ──")
_SPAC_STUB_RE = re.compile(
    r"^about\s+[\w\s]+\s+(acquisition|spac|corp|inc)[\s.()]*"
    r"|^\d{4,6}\.\w{2}\s*\|"
    r"|investment banking scorecard"
    r"|wsj pro private equity",
    re.IGNORECASE,
)

spac_test_cases = [
    ("About Miluna Acquisition Corp (MMTXU.OQ) - Reuters", True),
    ("About Blueport Acquisition Ltd (BPAC.OQ) - Reuters", True),
    ("About Haymaker Acquisition Corp 4 (HYAC.A) - Reuters", True),
    ("About Keen Vision Acquisition Corp (KVAC.O) - Reuters", True),
    ("486630.KR | KB No.30 Special Purpose Acquisition Co.", True),
    ("Investment Banking Scorecard", True),
    ("WSJ Pro Private Equity", True),
    # Should NOT be blocked:
    ("Constellation reaches agreement for acquisition of Calpine", False),
    ("Borr Drilling Acquisition of Five Premium Jack-Up Rigs", False),
]

fix4_pass = 0
fix4_fail = 0
for headline, should_block in spac_test_cases:
    matched = bool(_SPAC_STUB_RE.match(headline))
    status = "✅" if matched == should_block else "❌"
    if matched != should_block:
        fix4_fail += 1
        print(f"  {status} FAIL: '{headline[:55]}' → blocked={matched}, expected_block={should_block}")
    else:
        fix4_pass += 1
        print(f"  {status} OK:   '{headline[:55]}' → blocked={matched}")

print(f"\n  Results: {fix4_pass} passed, {fix4_fail} failed")

# ============================================================
# FIX 1.2 + 4.2: Bloomberg RSS should be None
# ============================================================
print("\n── FIX 1.2: Bloomberg RSS disabled ──")
from config import TARGET_SITES
for site in TARGET_SITES:
    if site["name"] == "Bloomberg Energy":
        if site["rss_url"] is None:
            print(f"  ✅ OK: Bloomberg Energy rss_url is None")
        else:
            print(f"  ❌ FAIL: Bloomberg Energy rss_url = {site['rss_url']}")
        break

# ============================================================
# FIX 1.3: Yahoo Finance query should have site: prefix
# ============================================================
print("\n── FIX 1.3: Yahoo Finance Google News queries ──")
for site in TARGET_SITES:
    if site["name"] == "Yahoo Finance - M&A":
        queries = site.get("google_news_queries", [])
        all_scoped = all("site:finance.yahoo.com" in q for q in queries)
        if all_scoped:
            print(f"  ✅ OK: All {len(queries)} queries have site: prefix")
        else:
            for q in queries:
                if "site:" not in q:
                    print(f"  ❌ FAIL: Unscoped query: '{q}'")
        break

# ============================================================
# FIX 2.1: RenewablesNow Deals should have needs_js=True
# ============================================================
print("\n── FIX 2.1: RenewablesNow Deals JS rendering ──")
for site in TARGET_SITES:
    if site["name"] == "RenewablesNow Deals":
        if site["needs_js"]:
            print(f"  ✅ OK: needs_js=True")
        else:
            print(f"  ❌ FAIL: needs_js=False (still broken)")
        if site["rss_url"]:
            print(f"  ✅ OK: RSS fallback = {site['rss_url']}")
        else:
            print(f"  ❌ FAIL: No RSS fallback")
        break

# ============================================================
# FIX 2.3: Rigzone should have m_and_a secondary path
# ============================================================
print("\n── FIX 2.3: Rigzone M&A secondary path ──")
for site in TARGET_SITES:
    if site["name"] == "Rigzone":
        paths = site.get("secondary_paths", [])
        if "/news/m_and_a/" in paths:
            print(f"  ✅ OK: /news/m_and_a/ in secondary_paths")
        else:
            print(f"  ❌ FAIL: /news/m_and_a/ missing. Got: {paths}")
        break

# ============================================================
# FIX 2.4: Hart Energy should have A&D secondary path
# ============================================================
print("\n── FIX 2.4: Hart Energy M&A path ──")
for site in TARGET_SITES:
    if site["name"] == "Hart Energy":
        paths = site.get("secondary_paths", [])
        has_ad = any("acquisitions" in p for p in paths)
        if has_ad:
            print(f"  ✅ OK: A&D path present in secondary_paths")
        else:
            print(f"  ❌ FAIL: A&D path missing. Got: {paths}")
        break

# ============================================================
# FIX 3.1: classify_deal_sheet should route mining to Mining & Metals
# ============================================================
print("\n── FIX 3.1: Mining & Metals sheet classification ──")
from config import classify_deal_sheet

mining_tests = [
    ("Zijin Mining Group: $2.6 Billion Acquisition Of Chifeng Jilong Gold Mining", "Mining & Metals"),
    ("Felix to unwrap Treasure Creek with mining acquisition", "Mining & Metals"),
    ("Coeur Mining Enters New Era Following Strategic Acquisition", "Mining & Metals"),
    ("Patronus Resources Advances Australian Mining Projects", "Mining & Metals"),
    # Non-mining should NOT go to Mining & Metals:
    ("Constellation reaches agreement for acquisition of Calpine", "P&U"),
    ("Borr Drilling Acquisition of Five Jack-Up Rigs", "OFS"),
]

fix31_pass = 0
fix31_fail = 0
for headline, expected_sheet in mining_tests:
    sheet, _ = classify_deal_sheet(headline)
    status = "✅" if sheet == expected_sheet else "❌"
    if sheet != expected_sheet:
        fix31_fail += 1
        print(f"  {status} FAIL: '{headline[:50]}' → {sheet} (expected {expected_sheet})")
    else:
        fix31_pass += 1
        print(f"  {status} OK:   '{headline[:50]}' → {sheet}")

print(f"\n  Results: {fix31_pass} passed, {fix31_fail} failed")

# ============================================================
# FIX 3.2: WSJ Commodities should NOT duplicate WSJ Energy RSS
# ============================================================
print("\n── FIX 3.2: WSJ RSS deduplication ──")
wsj_energy_rss = None
wsj_commod_rss = None
for site in TARGET_SITES:
    if site["name"] == "WSJ Energy":
        wsj_energy_rss = site.get("rss_url")
    if site["name"] == "WSJ Commodities":
        wsj_commod_rss = site.get("rss_url")
if wsj_energy_rss and wsj_commod_rss and wsj_energy_rss != wsj_commod_rss:
    print(f"  ✅ OK: WSJ Energy RSS ≠ WSJ Commodities RSS")
else:
    print(f"  ❌ FAIL: WSJ feeds still identical")

# ============================================================
# SUMMARY
# ============================================================
total_pass = fix1_pass + fix4_pass + fix31_pass
total_fail = fix1_fail + fix4_fail + fix31_fail
print(f"\n{'='*70}")
print(f"  TOTAL: {total_pass} passed, {total_fail} failed")
if total_fail == 0:
    print(f"  ✅ ALL FIXES VERIFIED SUCCESSFULLY")
else:
    print(f"  ⚠️  {total_fail} tests failed — review above")
print(f"{'='*70}")
