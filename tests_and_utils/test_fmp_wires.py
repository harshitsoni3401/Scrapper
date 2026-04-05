import asyncio
import aiohttp
import json
import os

async def test_fmp_wires():
    # Use a demo key or check if the endpoint is public without key for a single test
    # The M&A endpoint usually requires a key, but we can check the documentation or format
    url = "https://financialmodelingprep.com/api/v4/mergers-acquisitions-rss-feed?page=0&apikey=demo"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as response:
                print(f"FMP Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"FMP returned {len(data)} items.")
                    sources = set()
                    for item in data[:50]: # Look at first 50
                        # Try to find a source field or infer from URL
                        url_str = item.get('url', '')
                        if 'businesswire' in url_str: sources.add('BusinessWire')
                        elif 'prnewswire' in url_str: sources.add('PR Newswire')
                        elif 'globenewswire' in url_str: sources.add('GlobeNewswire')
                        else:
                            # Just print a few to see the structure
                            if len(sources) < 3:
                                sources.add(url_str.split('/')[2] if '//' in url_str else 'Unknown')
                    
                    print(f"FMP Sources found: {sources}")
                else:
                    text = await response.text()
                    print(f"FMP Error: {text}")
        except Exception as e:
            print(f"FMP Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_fmp_wires())
