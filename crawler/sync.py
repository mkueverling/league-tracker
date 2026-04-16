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

# --- NEW: EASY RESUME VARIABLE ---
START_PAGE = 52

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def fetch_player_details(slug):
    """Extracts smurfs and all social handles from the profile page via HTML."""
    url = f"https://lolpros.gg/player/{slug}"
    default_socials = {"twitch": None, "twitter": None, "youtube": None}
    
    try:
        response = requests.get(url, headers=SCRAPER_HEADERS, timeout=15)
        if response.status_code != 200:
            return {"accounts": [], "socials": default_socials}

        accounts = []
        socials = default_socials.copy()
        first_seen_account = None
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. HTML Scraping with Fallback Logic
        for p in soup.find_all(['p', 'span']):
            text = p.get_text(strip=True)
            
            # Check if it looks like a Riot ID
            if '#' in text and len(text.split('#')) == 2:
                name, tag = text.split('#')
                current_acc = {"game_name": name.strip(), "tag_line": tag.strip()}
                
                # Remember the very first valid Riot ID we see on the entire page
                if first_seen_account is None:
                    first_seen_account = current_acc
                
                # Look at the "box" (parent div) this text lives inside
                parent_box = p.find_parent('div')
                
                # If the box contains an image, it's an Active Account Card
                if parent_box and parent_box.find('img'):
                    # Prevent duplicates
                    if not any(acc['game_name'] == current_acc['game_name'] and acc['tag_line'] == current_acc['tag_line'] for acc in accounts):
                        accounts.append(current_acc)

        # 2. FALLBACK: If no image cards existed, use the first Riot ID found
        if len(accounts) == 0 and first_seen_account is not None:
            accounts.append(first_seen_account)

        # 3. Socials HTML Extraction
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
        return {"accounts": [], "socials": default_socials}

def sync_everything():
    print(f"DEBUG: Starting Global Sync with Riot API Key -> {str(API_KEY)[:10]}...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- CHANGED: NOW USES YOUR CONFIG VARIABLE ---
    page = START_PAGE
    total_new_pros = 0

    while True:
        ladder_url = f"https://api.lolpros.gg/es/ladder?page={page}&page_size=100&sort=rank&order=desc"
        print(f"\n--- SCRAPING LADDER PAGE {page} ---")
        
        res = requests.get(ladder_url, headers=SCRAPER_HEADERS)
        if res.status_code != 200:
            print("Reached end of ladder or hit a block. Stopping.")
            break
            
        pros_on_page = res.json()
        if not pros_on_page:
            break

        for p_meta in pros_on_page:
            slug = p_meta.get('slug')
            pro_name = p_meta.get('name')
            if not slug: continue

            # Pacing for LOLPros to prevent Cloudflare blocks
            time.sleep(1.5) 
            
            details = fetch_player_details(slug)
            print(f"\n[PRO: {pro_name}]")
            print(f"   Discovered {len(details['accounts'])} accounts on profile.")

            # Insert/Update Pro Master
            cursor.execute("""
                INSERT INTO Pros (name, twitch_url, twitter_url, youtube_url) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET 
                    twitch_url = EXCLUDED.twitch_url,
                    twitter_url = EXCLUDED.twitter_url,
                    youtube_url = EXCLUDED.youtube_url
                RETURNING pro_id;
            """, (pro_name, details['socials']['twitch'], details['socials']['twitter'], details['socials']['youtube']))
            pro_id = cursor.fetchone()[0]

            # Process Accounts with detailed terminal feedback
            for acc in details['accounts']:
                riot_id = f"{acc['game_name']}#{acc['tag_line']}"
                
                # Check DB first for the specific smurf
                cursor.execute("SELECT 1 FROM Accounts WHERE riot_id = %s", (riot_id,))
                if cursor.fetchone():
                    print(f"   -> [SKIPPED] {riot_id} (Already in DB)")
                    continue

                # Pacing for Riot API
                time.sleep(1.25) 
                
                safe_name = urllib.parse.quote(acc['game_name'])
                safe_tag = urllib.parse.quote(acc['tag_line'])
                riot_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
                
                riot_res = requests.get(riot_url, headers=RIOT_HEADERS)
                
                if riot_res.status_code == 200:
                    puuid = riot_res.json()['puuid']
                    cursor.execute("""
                        INSERT INTO Accounts (puuid, pro_id, riot_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (puuid) DO UPDATE SET riot_id = EXCLUDED.riot_id;
                    """, (puuid, pro_id, riot_id))
                    print(f"   -> [SUCCESS] {riot_id} (Added to DB)")
                
                elif riot_res.status_code == 404:
                    print(f"   -> [FAILED]  {riot_id} (Not found in Riot API - Player likely changed name)")
                elif riot_res.status_code == 429:
                    print(f"   -> [WARNING] {riot_id} (Rate limited by Riot! Sleeping 30s...)")
                    time.sleep(30)
                else:
                    print(f"   -> [FAILED]  {riot_id} (Riot HTTP {riot_res.status_code})")
            
            conn.commit()
            total_new_pros += 1

        page += 1 
    
    cursor.close()
    conn.close()
    print(f"\n--- Global Sync Complete. Total Pros Processed This Run: {total_new_pros} ---")

if __name__ == "__main__":
    sync_everything()