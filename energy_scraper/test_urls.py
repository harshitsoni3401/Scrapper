import asyncio
from config import TARGET_SITES
from fetcher import fetch_google_news_rss_raw

async def test_feeds():
    print("Testing Google News RSS queries for the 3 missing sites:")
    sites_to_test = [s for s in TARGET_SITES if s['name'] in [
        'BusinessWire - Energy', 'PR Newswire - Energy', 'GlobeNewswire - Energy'
    ]]
    
    for site in sites_to_test:
        print(f"\n--- {site['name']} ---")
        queries = site.get('google_news_queries', [])
        for q in queries:
            print(f" Query: {q}")
            articles = await fetch_google_news_rss_raw(q)
            print(f" Found: {len(articles)} articles")
            for a in articles[:3]:
                print(f"   - {a['title'][:80]}")
            
if __name__ == "__main__":
    asyncio.run(test_feeds())
