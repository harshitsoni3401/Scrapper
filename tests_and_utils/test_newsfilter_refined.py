import asyncio
import aiohttp
import json

async def test_newsfilter_refined():
    url = "https://api.newsfilter.io/public/actions"
    # Essential Lucene query for energy M&A
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
                    articles = data.get('articles', [])
                    print(f"Found {len(articles)} articles.")
                    for art in articles[:3]:
                        print(f"- {art.get('title')} ({art.get('source', {}).get('name')})")
                        print(f"  URL: {art.get('url')}")
                else:
                    text = await response.text()
                    print(f"Error: {text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_newsfilter_refined())
