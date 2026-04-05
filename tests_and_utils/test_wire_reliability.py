import asyncio
import feedparser
import urllib.parse
from bs4 import BeautifulSoup
import aiohttp

async def test_wire_feeds():
    feeds = {
        "BusinessWire (M&A)": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEVtRXA==",
        "GlobeNewswire (M&A)": "https://www.globenewswire.com/RssFeed/subjectcode/14-Mergers%20and%20Acquisitions/feedTitle/GlobeNewswire%20-%20Mergers%20and%20Acquisitions",
        "PR Newswire (Energy)": "https://www.prnewswire.com/rss/energy-latest-news/energy-latest-news-list.rss",
        "Google News (PR Newswire Energy)": f"https://news.google.com/rss/search?q={urllib.parse.quote_plus('site:prnewswire.com energy acquisition OR merger')}&hl=en-US&gl=US&ceid=US:en",
        "Google News (BusinessWire M&A)": f"https://news.google.com/rss/search?q={urllib.parse.quote_plus('site:businesswire.com energy acquisition OR merger')}&hl=en-US&gl=US&ceid=US:en",
    }
    
    print("Testing Native RSS feeds via feedparser...")
    for name, url in feeds.items():
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            if feed.entries:
                print(f"✅ {name}: Found {len(feed.entries)} entries. Latest: {feed.entries[0].title[:60]}")
            else:
                print(f"❌ {name}: Returned 0 entries or failed.")
        except Exception as e:
            print(f"❌ {name}: Exception {e}")

    print("\nTesting raw HTML fetch for the requested URLs...")
    urls = [
         "https://www.businesswire.com/newsroom/subject/merger-acquisition",
         "https://www.globenewswire.com/newsroom",
         "https://www.prnewswire.com/news-releases/energy-latest-news/energy-latest-news-list/"
    ]
    async with aiohttp.ClientSession() as session:
        for u in urls:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                async with session.get(u, headers=headers, timeout=10) as resp:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    title = soup.title.string if soup.title else "No Title"
                    print(f"{'✅' if resp.status == 200 else '❌'} HTML [{resp.status}] {u}")
                    print(f"    Title: {title.strip()}")
            except Exception as e:
                print(f"❌ HTML Exception for {u}: {e}")

if __name__ == "__main__":
    asyncio.run(test_wire_feeds())
