import feedparser
import urllib.parse

def test_query(query):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    lines = [f"\nQuery: {query}", f"URL: {url}"]
    feed = feedparser.parse(url)
    lines.append(f"Results: {len(feed.entries)}")
    if feed.entries:
        lines.append(f"Top 3:")
        for e in feed.entries[:3]:
            lines.append(f"  - {e.title}")
    return "\n".join(lines)

queries_to_test = [
    "site:businesswire.com energy acquisition OR merger",
    "site:businesswire.com energy M&A",
    "businesswire energy acquisition",
    "\"business wire\" energy acquisition",
    "BusinessWire \"energy\" \"acquisition\"",
    "site:businesswire.com \"energy\"",
    "businesswire.com energy AND (acquisition OR merger)"
]

out = []
for q in queries_to_test:
    out.append(test_query(q))

with open("test_gn_out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
