import asyncio
import aiohttp
import json

API_KEY = "P3AJrWsntVrH86dWsJD2NAlSYqs0xGda"

async def test_endpoints():
    async with aiohttp.ClientSession() as session:
        endpoints = {
            "M&A RSS Feed": f"https://financialmodelingprep.com/api/v4/mergers-acquisitions-rss-feed?page=0&apikey={API_KEY}",
            "M&A Search (energy)": f"https://financialmodelingprep.com/api/v4/mergers-acquisitions/search?name=energy&apikey={API_KEY}",
            "Press Releases": f"https://financialmodelingprep.com/api/v3/press-releases?page=0&apikey={API_KEY}",
            "Stock News": f"https://financialmodelingprep.com/api/v3/stock_news?page=0&apikey={API_KEY}",
            "General News": f"https://financialmodelingprep.com/api/v4/general_news?page=0&apikey={API_KEY}",
            "FMP Articles": f"https://financialmodelingprep.com/api/v3/fmp/articles?page=0&apikey={API_KEY}",
        }
        
        for name, url in endpoints.items():
            print(f"\n{'='*60}")
            print(f"  {name}")
            try:
                async with session.get(url, timeout=15) as resp:
                    status = resp.status
                    print(f"  Status: {status}")
                    if status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            print(f"  Items: {len(data)}")
                            if data:
                                print(f"  Keys: {list(data[0].keys())}")
                                # Print first item compactly
                                for k, v in data[0].items():
                                    val = str(v)[:80]
                                    print(f"    {k}: {val}")
                        elif isinstance(data, dict):
                            print(f"  Dict keys: {list(data.keys())}")
                            content = data.get('content', data.get('articles', []))
                            if isinstance(content, list) and content:
                                print(f"  Items in content: {len(content)}")
                                print(f"  Content keys: {list(content[0].keys())}")
                                for k, v in content[0].items():
                                    val = str(v)[:80]
                                    print(f"    {k}: {val}")
                    elif status == 403:
                        print(f"  BLOCKED (403) - Premium endpoint")
                    else:
                        text = await resp.text()
                        print(f"  Error: {text[:200]}")
            except Exception as e:
                print(f"  Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
