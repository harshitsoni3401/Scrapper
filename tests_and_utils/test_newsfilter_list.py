import asyncio
import aiohttp
import json

async def test_newsfilter_list():
    url = "https://api.newsfilter.io/public/actions"
    query = "(merger OR acquisition OR \"buy out\" OR divestiture) AND (energy OR oil OR gas OR solar OR wind)"
    payload = {
        "type": "filterArticles",
        "queryString": query,
        "from": 0,
        "size": 10
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                print(f"Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        print(f"Found {len(data)} items in list.")
                        for item in data[:2]:
                            if isinstance(item, dict):
                                print(f"- {item.get('title')} ({item.get('source', {}).get('name')})")
                            else:
                                print(f"- Non-dict item: {item}")
                    else:
                        print(f"Data is dict: {data.keys()}")
                else:
                    text = await response.text()
                    print(f"Error: {text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_newsfilter_list())
