from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "Codex_Handoff_Prompt.pdf"

TEXT = """Codex Handoff Prompt

Project
Active workspace: C:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run - Codex
Backup workspace: C:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run
Goal: professionalize an async Python energy and mining M&A scraper and continue work in Codex.

Current Status
- Standardized .venv setup and helper scripts.
- Fixed package imports for python -m energy_scraper.main.
- Added project_paths.py for repo-level runtime folders.
- Reports write to reports\\runs and logs to reports\\logs.
- Windows console encoding crashes were patched.
- browser.py was updated for current playwright-stealth compatibility.
- Fixed SEC-style collapsed timestamps like 2026-04-0106:20:52.
- Local tests pass: 33 passed.
- Live isolated checks were run for PR Newswire, BusinessWire family, and GlobeNewswire family.

Key Findings
- PR Newswire transport works best because direct RSS works.
- BusinessWire and GlobeNewswire are mostly fallback-driven through Google News, not reliable first-party extraction.
- Without AI keys loaded, the pipeline over-accepts false positives.
- With AI enabled from legacy env, false positives are reduced, but recall is still weak.
- The system is not near 100 percent efficiency for these publishers yet.

Root Causes
1. Repo-root .env is missing GROQ_API_KEY and GEMINI_API_KEY, while energy_scraper\\.env still has them.
2. BusinessWire and GlobeNewswire lack strong publisher-specific extraction paths.
3. Transaction classifier still confuses awards, financings, and non-M&A items with deals.
4. Google Sheets setup is noisy unless SPREADSHEET_ID is valid and shared correctly.

Recommended Plan
1. Unify environment loading so repo-root .env is the single source of truth.
2. Add provenance tracking for every accepted item: rss, direct_html, browser, cache, google_news.
3. Build publisher-specific extraction logic for PR Newswire, BusinessWire, and GlobeNewswire.
4. Tighten non-M&A rejection rules for awards, financings, contracts, earnings, filings, and market reports.
5. Add a benchmark harness for latest items per publisher with precision and recall measurement.
6. Make Google Sheets optional and quiet when SPREADSHEET_ID is not configured.

Test Commands
cd "C:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run - Codex"
.\\scripts\\Setup.ps1
.\\scripts\\Test-Project.ps1
.\\scripts\\Run-Scraper.ps1 -Start "31-03-2026" -End "01-04-2026" -Workers 1 -Sites "PR Newswire - Energy" -NoAggregator
.\\scripts\\Run-Scraper.ps1 -Start "31-03-2026" -End "01-04-2026" -Workers 1 -Sites "BusinessWire - M&A,BusinessWire - Energy,BusinessWire - Energy O&G,BusinessWire - Alternative Energy" -NoAggregator
.\\scripts\\Run-Scraper.ps1 -Start "31-03-2026" -End "01-04-2026" -Workers 1 -Sites "GlobeNewswire - Energy,GlobeNewswire - Oil & Gas Industries,GlobeNewswire - Renewables & Utilities,GlobeNewswire - Mining & Metals" -NoAggregator

Prompt For Next Codex Chat
Treat C:\\Users\\harsh\\OneDrive\\Desktop\\Scraper Trial Run - Codex as the active workspace. Read README.md first, then inspect energy_scraper\\main.py, scraper.py, fetcher.py, browser.py, ai_extractor.py, config.py, and project_paths.py. The project already has a standardized .venv and helper scripts. Do not redo old cleanup work. Focus on publisher-quality benchmarking and fixes for PR Newswire, BusinessWire, and GlobeNewswire. First, verify the single-source environment setup and make repo-root .env the authoritative config. Second, instrument provenance so each accepted item records whether it came from RSS, direct HTML, browser, cache, or Google News. Third, build publisher-specific extraction improvements and tighten non-M&A rejection rules for awards, financings, contracts, earnings, filings, and market reports. Fourth, create a benchmark harness that measures precision and recall on recent items from those publishers. Make changes directly in the repo, run tests, run narrow live checks, and summarize findings with concrete file references.
"""


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_lines(text: str, width: int = 92) -> list[str]:
    lines = []
    for raw in text.splitlines():
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        while len(raw) > width:
            split = raw.rfind(" ", 0, width)
            if split <= 0:
                split = width
            lines.append(raw[:split])
            raw = raw[split:].lstrip()
        lines.append(raw)
    return lines


def build_pdf_bytes(lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    margin_left = 50
    top = 740
    line_height = 14
    pages = []
    current = []
    y = top
    for line in lines:
        if y < 60:
            pages.append(current)
            current = []
            y = top
        current.append((margin_left, y, line))
        y -= line_height
    if current:
        pages.append(current)

    objects = []

    def add_object(data: str) -> int:
        objects.append(data.encode("latin-1"))
        return len(objects)

    font_obj = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    content_ids = []

    for page in pages:
        commands = ["BT", "/F1 11 Tf"]
        for x, y, line in page:
            safe = pdf_escape(line)
            commands.append(f"1 0 0 1 {x} {y} Tm ({safe}) Tj")
        commands.append("ET")
        stream = "\n".join(commands)
        content_id = add_object(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        content_ids.append(content_id)
        page_ids.append(None)

    pages_kids = []
    pages_id = None
    for idx, content_id in enumerate(content_ids):
        page_obj = f"<< /Type /Page /Parent {{PAGES}} 0 R /MediaBox [0 0 {page_width} {page_height}] /Contents {content_id} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
        page_id = add_object(page_obj)
        page_ids[idx] = page_id
        pages_kids.append(f"{page_id} 0 R")

    pages_dict = f"<< /Type /Pages /Kids [{' '.join(pages_kids)}] /Count {len(page_ids)} >>"
    pages_id = add_object(pages_dict)

    for idx, page_id in enumerate(page_ids):
        objects[page_id - 1] = objects[page_id - 1].replace(b"{PAGES}", str(pages_id).encode("latin-1"))

    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{i} 0 obj\n".encode("latin-1"))
        result.extend(obj)
        result.extend(b"\nendobj\n")
    xref_pos = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    result.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        result.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    result.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(result)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = wrap_lines(TEXT)
    OUTPUT_PATH.write_bytes(build_pdf_bytes(lines))
    print(f"Created {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
