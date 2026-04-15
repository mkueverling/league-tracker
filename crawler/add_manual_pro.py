import os
import requests
import time
import urllib.parse
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

# --- CONFIGURATION ---
# Automatically searches for the .env file in the current and parent directories
load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
RIOT_HEADERS = {"X-Riot-Token": API_KEY}

def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
    except Exception as e:
        print(f"[!] Could not connect to database: {e}")
        sys.exit(1)

def add_custom_pro():
    print("=== Manual Pro Entry Tool ===\n")
    
    # 1. Gather Pro Details
    pro_name = input("Enter Pro Name: ").strip()
    if not pro_name:
        print("Pro name cannot be empty. Exiting.")
        return

    print("\n(Press Enter to skip socials)")
    twitch = input("Twitch URL: ").strip() or None
    twitter = input("Twitter/X URL: ").strip() or None
    youtube = input("YouTube URL: ").strip() or None

    # 2. Gather Accounts
    accounts_to_add = []
    print("\nEnter Riot IDs one by one (format: Name#Tag).")
    print("When you are finished, just press Enter on an empty line.")
    
    while True:
        riot_id = input("> Riot ID: ").strip()
        if not riot_id:
            break
        if '#' not in riot_id:
            print("  [!] Invalid format. Must include a '#' (e.g., fthr#eu5)")
            continue
        accounts_to_add.append(riot_id)

    if not accounts_to_add:
        print("\nNo accounts entered. Exiting.")
        return

    # 3. Database & API Execution
    print(f"\n--- Saving {pro_name} and {len(accounts_to_add)} accounts to Database ---")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert the Pro
        cursor.execute("""
            INSERT INTO Pros (name, twitch_url, twitter_url, youtube_url) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET 
                twitch_url = COALESCE(EXCLUDED.twitch_url, Pros.twitch_url),
                twitter_url = COALESCE(EXCLUDED.twitter_url, Pros.twitter_url),
                youtube_url = COALESCE(EXCLUDED.youtube_url, Pros.youtube_url)
            RETURNING pro_id;
        """, (pro_name, twitch, twitter, youtube))
        
        pro_id = cursor.fetchone()[0]
        print(f"[✓] Created/Found Pro: {pro_name} (Database ID: {pro_id})")

        # Fetch PUUIDs and Insert Accounts
        for riot_id in accounts_to_add:
            game_name, tag_line = riot_id.split('#', 1)
            
            safe_name = urllib.parse.quote(game_name.strip())
            safe_tag = urllib.parse.quote(tag_line.strip())
            
            riot_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
            
            time.sleep(1.25) # Respect Riot Rate Limit
            response = requests.get(riot_url, headers=RIOT_HEADERS)
            
            if response.status_code == 200:
                puuid = response.json()['puuid']
                
                cursor.execute("""
                    INSERT INTO Accounts (puuid, pro_id, riot_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (puuid) DO UPDATE SET riot_id = EXCLUDED.riot_id;
                """, (puuid, pro_id, riot_id))
                
                print(f"   -> [SUCCESS] {riot_id} linked successfully.")
            
            elif response.status_code == 404:
                print(f"   -> [FAILED]  {riot_id} (Not found in Riot API. Check spelling.)")
            else:
                print(f"   -> [FAILED]  {riot_id} (Riot HTTP {response.status_code})")

        conn.commit()
        print("\n=== Manual Entry Complete ===")

    except Exception as e:
        print(f"\n[!] Database error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_custom_pro()