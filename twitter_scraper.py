import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('TWITTER_BEARER_TOKEN')}",
    "Cookie": os.getenv('TWITTER_COOKIE'),
    "User-Agent": os.getenv('TWITTER_USER_AGENT'),
    "X-Csrf-Token": os.getenv('TWITTER_CSRF_TOKEN'),
    "Referer": "https://x.com/home"
}

response = httpx.get(os.getenv('TWITTER_API_URL'), headers=headers)
 
if response.status_code == 200:
    data = response.json()
    with open("response_dump.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
