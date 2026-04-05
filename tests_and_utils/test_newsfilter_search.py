import asyncio
import aiohttp
import json

async def test_newsfilter_search():
    # Trying the /search endpoint mentioned in grounding
    url = "https://api.newsfilter.io/search"
    params = {
        "q": "energy merger acquisition",
        "size": 5
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=10) as response:
                print(f"Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    print(f"Found {len(articles)} articles.")
                    for art in articles[:2]:
                        print(f"- {art.get('title')} ({art.get('source', {}).get('name')})")
                else:
                    text = await response.text()
                    print(f"Error: {text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(test_newsfilter_search())
