import asyncio, aiohttp
from bs4 import BeautifulSoup
from energy_scraper.fetcher import fetch_static
from energy_scraper.scraper import _generic_article_parser

async def main():
    async with aiohttp.ClientSession() as s:
        h, sc, _, _ = await fetch_static('https://www.accessnewswire.com/newsroom/industry/metals-and-mining', s)
        print('HTTP: ', sc)
        print('HTML len: ', len(h))
        soup = BeautifulSoup(h, 'html.parser')
        res = _generic_article_parser(soup, 'https://www.accessnewswire.com')
        print('Articles found: ', len(res))

if __name__ == '__main__':
    asyncio.run(main())
