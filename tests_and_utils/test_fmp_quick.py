import asyncio
import aiohttp
import json

API_KEY = "P3AJrWsntVrH86dWsJD2NAlSYqs0xGda"
BASE = "https://financialmodelingprep.com"

async def test():
    endpoints = [
        ("M&A RSS", f"{BASE}/api/v4/mergers-acquisitions-rss-feed?page=0&apikey={API_KEY}"),
        ("M&A Search", f"{BASE}/api/v4/mergers-acquisitions/search?name=energy&apikey={API_KEY}"),
        ("Press Releases", f"{BASE}/api/v3/press-releases?page=0&apikey={API_KEY}"),
        ("Stock News", f"{BASE}/api/v3/stock_news?page=0&apikey={API_KEY}"),
        ("General News", f"{BASE}/api/v4/general_news?page=0&apikey={API_KEY}"),
        ("FMP Articles", f"{BASE}/api/v3/fmp/articles?page=0&apikey={API_KEY}"),
    ]
    async with aiohttp.ClientSession() as s:
        for name, url in endpoints:
            try:
                async with s.get(url, timeout=15) as r:
                    print(f"{name}: {r.status}", end="")
                    if r.status == 200:
                        d = await r.json()
                        if isinstance(d, list):
                            print(f" | {len(d)} items | keys={list(d[0].keys()) if d else '[]'}")
                        elif isinstance(d, dict):
                            for k2 in ['content','articles','data']:
                                if k2 in d and isinstance(d[k2], list) and d[k2]:
                                    print(f" | {len(d[k2])} items in '{k2}' | keys={list(d[k2][0].keys())}")
                                    break
                            else:
                                print(f" | dict keys={list(d.keys())}")
                    else:
                        print(" | BLOCKED")
            except Exception as e:
                print(f" | ERROR: {e}")

asyncio.run(test())
