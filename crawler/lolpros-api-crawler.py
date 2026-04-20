import os
import requests
import time
import psycopg2
import urllib.parse
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9" 
}

VALID_ROLES = {
    "Top", "Jungle", "Jungler", "Mid", "Bot", "ADC", "AD Carry", "Support", 
    "Coach", "Head Coach", "Assistant Coach", "Manager", "Sub", "Substitute"
}

VALID_COUNTRIES = {
    "France", "Germany", "Spain", "Poland", "Denmark", "Sweden", "United Kingdom", "UK", "Great Britain", "England", "Scotland", "Wales",
    "Italy", "Netherlands", "Norway", "Belgium", "Portugal", "Romania", "Greece", "Czech Republic", "Czechia", "Hungary", 
    "Austria", "Switzerland", "Bulgaria", "Serbia", "Croatia", "Finland", "Ireland", "Slovakia", "Lithuania", "Slovenia", 
    "Latvia", "Estonia", "Cyprus", "Luxembourg", "Malta", "Iceland", "Russia", "Ukraine", "Belarus", "Bosnia and Herzegovina", 
    "Turkey", "Türkiye", "Lebanon", "Egypt", "Morocco", "South Korea", "Korea", "Republic of Korea", "China", "Japan", 
    "Taiwan", "Vietnam", "USA", "United States", "Canada", "Brazil", "Australia"
}

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def fetch_player_details(slug):
    url = f"https://lolpros.gg/player/{slug}"
    details = {"accounts": [], "socials": {"twitch": None, "twitter": None, "youtube": None}, "roles": [], "nationalities": []}
    
    try:
        response = requests.get(url, headers=SCRAPER_HEADERS, timeout=15)
        if response.status_code != 200: return details
        soup = BeautifulSoup(response.text, 'html.parser')
        first_seen_account = None

        for el in soup.find_all(['p', 'span', 'div']):
            text = el.get_text(strip=True)
            if not text: continue

            if text in VALID_ROLES:
                norm_role = "Bot" if text in ["ADC", "AD Carry"] else "Jungle" if text == "Jungler" else text
                if norm_role not in details["roles"]: details["roles"].append(norm_role)
                
            elif text in VALID_COUNTRIES:
                norm_nat = text
                if text in ["UK", "Great Britain", "England", "Scotland", "Wales"]: norm_nat = "United Kingdom"
                elif text == "Türkiye": norm_nat = "Turkey"
                elif text in ["Korea", "Republic of Korea"]: norm_nat = "South Korea"
                if norm_nat not in details["nationalities"]: details["nationalities"].append(norm_nat)

            if '#' in text and len(text.split('#')) == 2:
                name, tag = text.split('#')
                if 2 <= len(name.strip()) <= 16 and 2 <= len(tag.strip()) <= 5:
                    current_acc = {"game_name": name.strip(), "tag_line": tag.strip()}
                    if first_seen_account is None: first_seen_account = current_acc
                    parent_box = el.find_parent('div')
                    if parent_box and parent_box.find('img'):
                        if not any(acc['game_name'] == current_acc['game_name'] and acc['tag_line'] == current_acc['tag_line'] for acc in details["accounts"]):
                            details["accounts"].append(current_acc)

        if not details["accounts"] and first_seen_account: details["accounts"].append(first_seen_account)

        for link in soup.find_all('a', href=True):
            href = link['href']
            if "twitch.tv" in href and not details["socials"]['twitch']: details["socials"]['twitch'] = href if href.startswith('http') else f"https:{href}"
            elif ("twitter.com" in href or "x.com" in href) and not details["socials"]['twitter']: details["socials"]['twitter'] = href if href.startswith('http') else f"https:{href}"
            elif ("youtube.com" in href or "youtu.be" in href) and not details["socials"]['youtube']: details["socials"]['youtube'] = href if href.startswith('http') else f"https:{href}"

        details["role_str"] = ", ".join(details["roles"]) if details["roles"] else None
        details["nat_str"] = ", ".join(details["nationalities"]) if details["nationalities"] else None
        return details
    except Exception as e:
        print(f"   [!] Error parsing {slug}: {e}"); return details

def sync_everything(start_page=1):
    print(f"DEBUG: Starting Global Sync at Page {start_page}...")
    conn = get_db_connection(); cursor = conn.cursor()
    page = start_page

    while True:
        ladder_url = f"https://api.lolpros.gg/es/ladder?page={page}&page_size=100&sort=rank&order=desc"
        print(f"\n--- SCRAPING LADDER PAGE {page} ---")
        res = requests.get(ladder_url, headers=SCRAPER_HEADERS)
        if res.status_code != 200: break
        pros_on_page = res.json()
        if not pros_on_page: break

        for p_meta in pros_on_page:
            slug = p_meta.get('slug', '').lower() 
            pro_name = p_meta.get('name')
            if not slug: continue

            time.sleep(1.0)
            details = fetch_player_details(slug)
            print(f"\n[PRO: {pro_name} | Roles: {details['role_str']} | Nat: {details['nat_str']}]")

            cursor.execute("""
                INSERT INTO players (name, known_name, role, nationality, twitch_url, twitter_url, youtube_url, is_creator) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (name) DO UPDATE SET 
                    known_name = COALESCE(players.known_name, EXCLUDED.known_name),
                    role = EXCLUDED.role, nationality = EXCLUDED.nationality,
                    twitch_url = COALESCE(EXCLUDED.twitch_url, players.twitch_url),
                    twitter_url = COALESCE(EXCLUDED.twitter_url, players.twitter_url),
                    youtube_url = COALESCE(EXCLUDED.youtube_url, players.youtube_url),
                    is_creator = TRUE
                RETURNING player_id;
            """, (slug, pro_name, details['role_str'], details['nat_str'], details['socials']['twitch'], details['socials']['twitter'], details['socials']['youtube']))
            player_id = cursor.fetchone()[0]

            for acc in details['accounts']:
                riot_id = f"{acc['game_name']}#{acc['tag_line']}"
                
                # Check if account exists
                cursor.execute("SELECT 1 FROM accounts WHERE riot_id = %s", (riot_id,))
                if cursor.fetchone():
                    print(f"   -> [SKIPPED] {riot_id} (Already in DB)")
                    continue

                time.sleep(1.2)
                safe_name, safe_tag = urllib.parse.quote(acc['game_name']), urllib.parse.quote(acc['tag_line'])
                riot_res = requests.get(f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}", headers=RIOT_HEADERS)
                
                if riot_res.status_code == 200:
                    puuid = riot_res.json()['puuid']
                    cursor.execute("INSERT INTO accounts (puuid, player_id, riot_id) VALUES (%s, %s, %s) ON CONFLICT (puuid) DO UPDATE SET riot_id = EXCLUDED.riot_id;", (puuid, player_id, riot_id))
                    print(f"   -> [ADDED] {riot_id}")
                elif riot_res.status_code == 429:
                    print("   -> [WARNING] Rate limited. Sleeping 30s..."); time.sleep(30)
            
            conn.commit()
        page += 1 
    cursor.close(); conn.close()

# --- INTERACTIVE PROMPT SETUP ---
if __name__ == "__main__":
    print("\n=== LOLPROS LADDER SCRAPER ===")
    user_input = input("Enter the starting page number (or press Enter to start from page 1): ")
    
    try:
        start_page = int(user_input) if user_input.strip() else 1
    except ValueError:
        print("Invalid input detected. Defaulting to page 1.")
        start_page = 1

    sync_everything(start_page=start_page)