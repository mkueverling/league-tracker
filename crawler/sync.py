import os
import requests
import time
import psycopg2
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Bulletproof path resolution
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
# ... existing code ...
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'

# ADD THESE TWO LINES:
print(f"DEBUG: Looking for .env file at -> {env_path}")
print(f"DEBUG: Does this file exist? -> {env_path.exists()}")

load_dotenv(dotenv_path=env_path)
# ... rest of the code ...
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

# Updated Active EUW players with correct Riot IDs and Socials
PRO_ACCOUNTS = [
    {
        "pro_name": "Jankos", 
        "game_name": "G2 Jankos", 
        "tag_line": "unc2",
        "twitch": "https://twitch.tv/jankos",
        "twitter": "https://x.com/G2Jankos",
        "youtube": "https://youtube.com/@Jankos"
    },
    {
        "pro_name": "Agurin", 
        "game_name": "Agurin", 
        "tag_line": "DND",
        "twitch": "https://twitch.tv/agurin",
        "twitter": "https://x.com/Agurinlol",
        "youtube": "https://youtube.com/@Agurin"
    },
        {
        "pro_name": "Bloodwork", 
        "game_name": "Spieljunge", 
        "tag_line": "8008",
        "twitch": "https://twitch.tv/jankos",
        "twitter": "https://x.com/G2Jankos",
        "youtube": "https://youtube.com/@Jankos"
    },
    {
        "pro_name": "Tolkin", 
        "game_name": "Tollkühn", 
        "tag_line": "azb",
        "twitch": "https://twitch.tv/tolkin",
        "twitter": "https://x.com/TolkinLoL",
        "youtube": "https://youtube.com/@Tolkin"
    }
]

def sync_pros():
    # Adding a quick debug print so you know if your key is actually loaded
    print(f"DEBUG: Using API Key starting with -> {str(API_KEY)[:10]}...")
    
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()

    for pro in PRO_ACCOUNTS:
        print(f"Processing {pro['pro_name']}...")
        
        # Insert into Pros table with social links
        cursor.execute("""
            INSERT INTO Pros (name, twitch_url, twitter_url, youtube_url) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE 
            SET twitch_url=EXCLUDED.twitch_url, twitter_url=EXCLUDED.twitter_url, youtube_url=EXCLUDED.youtube_url
            RETURNING pro_id;
        """, (pro['pro_name'], pro['twitch'], pro['twitter'], pro['youtube']))
        pro_id = cursor.fetchone()[0]

        # URL-Encode the game name and tag line to protect against spaces and special characters (like 'ü')
        safe_game_name = urllib.parse.quote(pro['game_name'])
        safe_tag_line = urllib.parse.quote(pro['tag_line'])

        # Extract PUUID from Riot API
        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_game_name}/{safe_tag_line}"
        res = requests.get(url, headers=HEADERS)
        
        if res.status_code == 200:
            puuid = res.json()['puuid']
            riot_id = f"{pro['game_name']}#{pro['tag_line']}"
            
            # Load into Accounts table
            cursor.execute("""
                INSERT INTO Accounts (puuid, pro_id, riot_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (puuid) DO UPDATE SET riot_id=EXCLUDED.riot_id;
            """, (puuid, pro_id, riot_id))
            print(f"Successfully synced {riot_id}")
        else:
            print(f"Failed to fetch Riot ID for {pro['pro_name']}: HTTP {res.status_code}")
            
        time.sleep(1.2)

    conn.commit()
    cursor.close()
    conn.close()
    print("Dimension load complete.")

if __name__ == "__main__":
    sync_pros()