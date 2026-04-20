import os
import requests
import time
import urllib.parse
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

# --- CONFIGURATION ---
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
    print("=== Manual Pro Entry Tool (Unified Schema) ===\n")
    
    known_name = input("Enter Pro/Known Name: ").strip()
    if not known_name:
        print("Name cannot be empty. Exiting.")
        return

    # NEW: Ask for a special tag
    special_tag = input("Enter Special Tag (e.g., THE DEV) or press Enter to skip: ").strip()
    if not special_tag:
        special_tag = None

    accounts_to_add = []
    print("\nEnter Riot IDs one by one (format: Name#Tag).")
    print("Press Enter on an empty line when finished.")
    
    while True:
        riot_id = input("> Riot ID: ").strip()
        if not riot_id:
            break
        if '#' not in riot_id:
            print("  [!] Invalid format. Must include a '#' (e.g., Agurin#EUW)")
            continue
        accounts_to_add.append(riot_id)

    if not accounts_to_add:
        print("\nNo accounts entered. Exiting.")
        return

    print(f"\n--- Saving {known_name} and {len(accounts_to_add)} accounts ---")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        slug_name = known_name.lower().replace(" ", "-")
        
        # Determine if they are a creator based on if they got a special tag
        is_creator = True if special_tag else False
        
        cursor.execute("""
            INSERT INTO players (name, known_name, is_pro, is_creator, special_tag) 
            VALUES (%s, %s, TRUE, %s, %s)
            ON CONFLICT (name) DO UPDATE SET 
                known_name = COALESCE(players.known_name, EXCLUDED.known_name),
                is_pro = TRUE,
                is_creator = EXCLUDED.is_creator,
                special_tag = COALESCE(EXCLUDED.special_tag, players.special_tag)
            RETURNING player_id;
        """, (slug_name, known_name, is_creator, special_tag))
        
        player_id = cursor.fetchone()[0]
        print(f"[✓] Player Record Ready: {known_name} (ID: {player_id})")

        for riot_id in accounts_to_add:
            game_name, tag_line = riot_id.split('#', 1)
            safe_name = urllib.parse.quote(game_name.strip())
            safe_tag = urllib.parse.quote(tag_line.strip())
            
            riot_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
            
            time.sleep(1.2)
            response = requests.get(riot_url, headers=RIOT_HEADERS)
            
            if response.status_code == 200:
                puuid = response.json()['puuid']
                
                cursor.execute("""
                    INSERT INTO accounts (puuid, player_id, riot_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (puuid) DO UPDATE SET 
                        riot_id = EXCLUDED.riot_id,
                        player_id = EXCLUDED.player_id;
                """, (puuid, player_id, riot_id))
                
                print(f"   -> [SUCCESS] {riot_id} linked.")
            else:
                print(f"   -> [FAILED]  {riot_id} (HTTP {response.status_code})")

        conn.commit()
        print("\n=== Manual Entry Complete ===")

    except Exception as e:
        print(f"\n[!] error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_custom_pro()