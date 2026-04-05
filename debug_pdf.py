"""Debug script to capture full traceback from generate_reports.py"""
import traceback
import sys

sys.path.insert(0, "energy_scraper")
try:
    import generate_reports
    generate_reports.build_how_it_works()
except Exception:
    traceback.print_exc()
