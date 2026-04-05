"""Quick standalone test of the AsyncNewsAggregator — writes to file."""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "energy_scraper"))
logging.basicConfig(level=logging.INFO, format="%(message)s")

from news_aggregator import AsyncNewsAggregator

async def test():
    agg = AsyncNewsAggregator(
        start_date="2026-03-23",
        end_date="2026-03-26",
    )
    candidates = await agg.collect_all()
    
    sources = {}
    for c in candidates:
        src = c.get("source", "Unknown")
        src_key = src.split(":")[0].strip() if ":" in src else src
        sources[src_key] = sources.get(src_key, 0) + 1
    
    wire_count = sum(1 for c in candidates if any(w in c['url'].lower() for w in ['businesswire', 'prnewswire', 'globenewswire']))

    lines = []
    lines.append(f"Total unique candidates: {len(candidates)}")
    lines.append(f"Wire service articles (BW + PRN + GNW): {wire_count}")
    lines.append(f"\nBy source:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        lines.append(f"  {src}: {count}")
    lines.append(f"\nSample headlines (first 15):")
    for c in candidates[:15]:
        lines.append(f"  [{c.get('source','?')[:25]}] {c['headline'][:90]}")
    
    with open("aggregator_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Done. Saved to aggregator_results.txt")

asyncio.run(test())
