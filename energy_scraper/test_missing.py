import asyncio
import logging
from fetcher import AsyncSmartFetcher, fetch_static
import aiohttp
from extractor import DealExtractor
from utils import parse_date
from datetime import datetime
import json

urls = [
    "https://www.businesswire.com/news/home/20260319869411/en/Kodiak-Gas-Services-Announces-Accretive-Purchase-of-Over-20000-Horsepower-in-the-Permian-Basin",
    "https://www.prnewswire.com/news-releases/hawkins-lease-service-inc-family-of-businesses-expands-permian-basin-footprint-with-acquisition-of-knock-out-energy-llc-302721436.html",
    "https://www.prnewswire.com/news-releases/borr-drilling-limited--acquisition-of-five-premium-jack-up-rigs-through-new-joint-venture-302722572.html",
    "https://www.energy-pedia.com/news/france/technip-energies-invests-in-verso-energy%E2%80%99s-dezir-esaf-project-in-rouen-203281",
    "https://www.globenewswire.com/news-release/2026/03/23/3260396/0/en/Critical-Metals-Corp-Nasdaq-CRML-Announces-the-Successful-Acquisition-of-the-Leading-Turn-Key-Engineering-Mining-Construction-Infrastructure-Drilling-Operator-Within-Greenland-60-D.html",
    "https://renewablesnow.com/news/canadas-axium-buys-stake-in-174-2-mw-wind-farm-portfolio-in-france-1291813/",
    "https://www.globenewswire.com/news-release/2026/03/24/3261225/0/en/GoldHaven-Expands-Magno-Project-to-Over-37-200-Hectares-with-Strategic-Cassiar-Claims-Acquisition.html",
    "https://www.globenewswire.com/news-release/2026/03/24/3261067/0/en/Copper-Quest-Expands-its-Kitimat-Copper-Gold-Project-on-the-Strength-of-the-AI-Generated-Porphyry-Target.html",
    "https://expro.com.ua/novini/okko-vikupilo-prokt-ves-u-kolishnogo-ternoplskogo-chinovnika",
    "https://www.bloomberg.com/news/articles/2026-03-24/form-energy-sells-batteries-to-crusoe-to-power-new-data-centers?srnd=phx-industries-energy",
    "https://www.globenewswire.com/news-release/2026/03/24/3261725/0/en/Comstock-Announces-Full-Year-2025-Achievements-and-Results.html"
]

async def analyze():
    extractor = DealExtractor()
    start = datetime.strptime("23-03-2026", "%d-%m-%Y").date()
    end = datetime.strptime("24-03-2026", "%d-%m-%Y").date()

    with open("test_missing_clean.log", "w", encoding="utf-8") as f:
        async with aiohttp.ClientSession() as session:
            for url in urls:
                f.write(f"\n--- URL: {url} ---\n")
                html, sc, access_mode, render_type = await fetch_static(url, session)
                if not html or len(html) < 200:
                    f.write(" ❌ Failed to fetch\n")
                    continue
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                headline = soup.title.string if soup.title else ""
                if "robot" in headline.lower() or "captcha" in headline.lower() or "forbidden" in headline.lower():
                    slug = url.split("/")[-1].split("?")[0]
                    headline = slug.replace("-", " ").title()
                    f.write(f" Headline (Fallback): {headline.strip()}\n")
                
                # extraction
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                body_text = " ".join(soup.stripped_strings)[:3000]
                
                raw_date = None
                date_meta = soup.find("meta", {"property": "article:published_time"})
                if date_meta: raw_date = date_meta.get("content")
                
                # date parsing
                d_str = parse_date(raw_date or "")
                if d_str:
                    d = datetime.strptime(d_str, "%Y-%m-%d").date()
                    in_range = start <= d <= end
                    f.write(f" Date Output: {d_str} (in range: {in_range})\n")
                else:
                    f.write(f" Date parse failed\n")
                
                # confidence
                conf = extractor.compute_confidence(headline, body_text, False)
                f.write(f" Confidence: {conf}\n")
                
                # AI Check
                if conf >= 0.15:
                    res = await extractor.ai.verify_is_deal(headline, body_text[:1000])
                    f.write(f" AI Verification: {res}\n")
                else:
                    f.write(" ❌ Blocked by confidence < 0.15\n")

if __name__ == "__main__":
    asyncio.run(analyze())
