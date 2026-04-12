import os
import requests
import time
import psycopg2
import urllib.parse
import re
import json
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("RIOT_API_KEY")
RIOT_HEADERS = {"X-Riot-Token": API_KEY}
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def fetch_player_details(slug):
    """Extracts smurfs and all social handles from the profile page."""
    url = f"https://lolpros.gg/player/{slug}"
    print(f"   --> Deep diving: {url}")
    
    try:
        response = requests.get(url, headers=SCRAPER_HEADERS, timeout=10)
        if response.status_code != 200:
            return {"accounts": [], "socials": {}}

        # 1. JSON Extraction
        json_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
        match = re.search(json_pattern, response.text, re.DOTALL)
        
        accounts = []
        socials = {"twitch": None, "twitter": None, "youtube": None}

        if match:
            full_data = json.loads(match.group(1))
            player_data = full_data.get('props', {}).get('pageProps', {}).get('player', {})
            
            raw_accounts = player_data.get('accounts', [])
            for acc in raw_accounts:
                name = acc.get('riot_id_name')
                tag = acc.get('riot_id_tag')
                if name and tag:
                    accounts.append({"game_name": name.strip(), "tag_line": tag.strip()})
            
            s = player_data.get('socials', {})
            if s.get('twitch'): socials['twitch'] = f"https://twitch.tv/{s['twitch']}"
            if s.get('twitter'): socials['twitter'] = f"https://x.com/{s['twitter']}"
            if s.get('youtube'): socials['youtube'] = f"https://youtube.com/{s['youtube']}"

        # 2. HTML Fallback for Socials
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if "twitch.tv" in href and not socials['twitch']:
                socials['twitch'] = href if href.startswith('http') else f"https:{href}"
            elif ("twitter.com" in href or "x.com" in href) and not socials['twitter']:
                socials['twitter'] = href if href.startswith('http') else f"https:{href}"
            elif ("youtube.com" in href or "youtu.be" in href) and not socials['youtube']:
                socials['youtube'] = href if href.startswith('http') else f"https:{href}"

        return {"accounts": accounts, "socials": socials}

    except Exception as e:
        print(f"   [!] Error parsing {slug}: {e}")
        return {"accounts": [], "socials": {}}

def sync_everything():
    print(f"DEBUG: Starting Global Sync...")
    conn = get_db_connection()
    cursor = conn.cursor()

    page = 1
    total_new_pros = 0

    while True:
        # Step 1: Request the current page
        ladder_url = f"https://api.lolpros.gg/es/ladder?page={page}&page_size=100&sort=rank&order=desc"
        print(f"\n--- SCRAPING LADDER PAGE {page} ---")
        
        res = requests.get(ladder_url, headers=SCRAPER_HEADERS)
        if res.status_code != 200:
            print("Reached end of ladder or hit a block. Stopping.")
            break
            
        pros_on_page = res.json()
        if not pros_on_page: # Stop if the page is empty
            break

        for p_meta in pros_on_page:
            slug = p_meta.get('slug')
            if not slug: continue
            
            # Stage 2: Deep Dive (Smurfs & Socials)
            details = fetch_player_details(slug)
            print(f"   [PRO: {p_meta.get('name')}]")

            # DB Update Logic
            cursor.execute("""
                INSERT INTO Pros (name, twitch_url, twitter_url, youtube_url) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET 
                    twitch_url = EXCLUDED.twitch_url,
                    twitter_url = EXCLUDED.twitter_url,
                    youtube_url = EXCLUDED.youtube_url
                RETURNING pro_id;
            """, (p_meta.get('name'), details['socials']['twitch'], details['socials']['twitter'], details['socials']['youtube']))
            pro_id = cursor.fetchone()[0]

            for acc in details['accounts']:
                # (Keep your existing Riot API / PUUID logic here...)
                # (Ensure time.sleep(1.2) is still there!)
                pass
            
            conn.commit()
            total_new_pros += 1

        page += 1 # Move to the next 100 players
    
    cursor.close()
    conn.close()
    print(f"\n--- Global Sync Complete. Total Pros Processed: {total_new_pros} ---")

if __name__ == "__main__":
    sync_everything()