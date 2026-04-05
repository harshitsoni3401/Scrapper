import os
import time
import random
import requests
from bs4 import BeautifulSoup
import dateutil.parser
from datetime import datetime

# Common User Agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

def fetch_url(url, method="A", max_retries=2):
    """
    Fetches a URL with basic randomized delays and headers.
    Returns (html_content, status_code, fetch_method, access_mode, render_type)
    method="A" means direct HTTP request.
    """
    render_type = "Static"
    for attempt in range(max_retries):
        try:
            # Randomized delay between 2 to 5 seconds
            time.sleep(random.uniform(1.0, 2.5))
            
            headers = get_random_headers()
            # Timeout 15 seconds per prompt
            response = requests.get(url, headers=headers, timeout=15)
            
            access_mode = "Full"
            if response.status_code == 403 or "paywall" in response.text.lower():
                access_mode = "Blocked" if response.status_code == 403 else "Paywall/Auth-Required"
                render_type = "Paywall"
                
            return response.text, response.status_code, method, access_mode, render_type
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return "", str(e), method, "Failed", "Static"
            continue
            
    return "", "Unknown Error", method, "Failed", "Static"

def parse_date(date_str, format="%Y-%m-%d"):
    """
    Normalize date string to YYYY-MM-DD.
    """
    if not date_str:
        return None
    try:
        dt = dateutil.parser.parse(date_str, fuzzy=True)
        return dt.strftime(format)
    except Exception:
        # Cannot parse
        return None

def is_within_date_range(parsed_date, start_date, end_date):
    """
    Compare YYYY-MM-DD with start_date and end_date
    """
    if not parsed_date:
        return False
        
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    p_dt = datetime.strptime(parsed_date, "%Y-%m-%d").date()
    
    return start_dt <= p_dt <= end_dt
