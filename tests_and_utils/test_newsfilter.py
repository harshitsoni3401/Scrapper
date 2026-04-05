import asyncio
import aiohttp
import json

async def test_newsfilter():
    url = "https://api.newsfilter.io/public/actions"
    payload = {
        "type": "filterArticles",
        "queryString": "merger",
        "from": 0,
        "size": 5
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=10) as response:
                print(f"Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Found {len(data.get('articles', []))} articles.")
                    for art in data.get('articles', [])[:2]:
                        print(f"- {art.get('title')} ({art.get('source', {}).get('name')})")
                else:
                    text = await response.text()
                    print(f"Error: {text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_newsfilter())
