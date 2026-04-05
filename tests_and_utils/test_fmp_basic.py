import asyncio
import aiohttp

API_KEY = "P3AJrWsntVrH86dWsJD2NAlSYqs0xGda"
BASE = "https://financialmodelingprep.com"

async def test():
    # Try endpoints known to work on free tier per FMP docs
    endpoints = [
        ("Company Profile", f"{BASE}/api/v3/profile/AAPL?apikey={API_KEY}"),
        ("Quote", f"{BASE}/api/v3/quote/AAPL?apikey={API_KEY}"),
        ("Search", f"{BASE}/api/v3/search?query=energy&limit=5&apikey={API_KEY}"),
        ("Stock Screener", f"{BASE}/api/v3/stock-screener?marketCapMoreThan=1000000000&sector=Energy&limit=5&apikey={API_KEY}"),
        ("Key Metrics", f"{BASE}/api/v3/key-metrics/AAPL?limit=1&apikey={API_KEY}"),
    ]
    async with aiohttp.ClientSession() as s:
        for name, url in endpoints:
            try:
                async with s.get(url, timeout=15) as r:
                    print(f"{name}: {r.status}", end="")
                    if r.status == 200:
                        d = await r.json()
                        if isinstance(d, list):
                            print(f" | {len(d)} items")
                        elif isinstance(d, dict):
                            print(f" | keys={list(d.keys())[:5]}")
                    else:
                        t = await r.text()
                        print(f" | {t[:100]}")
            except Exception as e:
                print(f" | ERROR: {e}")

asyncio.run(test())
