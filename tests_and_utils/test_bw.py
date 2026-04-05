"""Test specific to BusinessWire M&A over the last 10 days."""
import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "energy_scraper"))

from news_aggregator import AsyncNewsAggregator
from config import is_energy_relevant

async def test_bw():
    start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    agg = AsyncNewsAggregator(start_date=start, end_date=end)
    candidates = await agg.collect_all()
    
    bw_cands = [c for c in candidates if "businesswire" in c.get("source", "").lower() or "businesswire" in c["url"].lower()]
    
    # Filter for energy relevance
    energy_cands = []
    for c in bw_cands:
        if is_energy_relevant(c["headline"], ""):
            energy_cands.append(c)

    lines = []
    lines.append(f"Found {len(bw_cands)} TOTAL BusinessWire candidates across aggregator.")
    lines.append(f"Found {len(energy_cands)} ENERGY RELEVANT BusinessWire candidates.")
    lines.append("\nALL ENERGY RELEVANT BUSINESSWIRE DEALS:")
    for c in energy_cands:
        lines.append(f"  [{c.get('source','?')}] {c['headline']}")
        lines.append(f"  URL: {c['url']}\n")
    lines.append(f"Found {len(bw_cands)} TOTAL BusinessWire candidates across aggregator.")
    lines.append("ALL BUSINESSWIRE HEADLINES:")
    for c in bw_cands:
        lines.append(f"  [{c.get('source','?')}] {c['headline']}")
        lines.append(f"  URL: {c['url']}")
        
    with open("test_bw_out_utf8.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Done")

if __name__ == "__main__":
    asyncio.run(test_bw())
