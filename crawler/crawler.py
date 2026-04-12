import requests
import time
import os
import psycopg2
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
REGION = "europe"

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def get_high_water_mark(cursor, puuid):
    """Finds the most recent match timestamp to prevent duplicate processing."""
    cursor.execute("""
        SELECT MAX(m.timestamp) 
        FROM Matches m
        JOIN Match_Participants mp ON m.match_id = mp.match_id
        WHERE mp.puuid = %s
    """, (puuid,))
    result = cursor.fetchone()[0]
    
    if result:
        # Convert ms to seconds and add 1s to start after the last game
        return int(result / 1000) + 1 
    return None

def process_incremental_load():
    print(f"DEBUG: Starting Crawler with Key -> {str(API_KEY)[:10]}...")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get every account we know about
    cursor.execute("SELECT puuid, riot_id FROM Accounts")
    accounts = cursor.fetchall()
    print(f"Targeting {len(accounts)} total accounts.")

    for puuid, riot_id in accounts:
        try:
            print(f"\n--- Checking {riot_id} ---")
            
            last_timestamp = get_high_water_mark(cursor, puuid)
            
            # LIMIT 10: Set count=10 for high-speed rotation across the whole ladder
            url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=10"
            
            if last_timestamp:
                url += f"&startTime={last_timestamp}"
            
            # 1. Fetch Match IDs
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"   [!] Error fetching match list: {response.status_code}")
                continue
                
            match_ids = response.json()
            if not match_ids:
                print("   No new matches found.")
                continue

            print(f"   Found {len(match_ids)} new matches. Processing...")

            # 2. Fetch Individual Match Details
            for match_id in match_ids:
                # SAFETY WRAPPER: Each match is processed independently
                try:
                    # Pacing: 1.25s is the sweet spot for dev keys (100 req / 120s)
                    time.sleep(1.25) 
                    
                    detail_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
                    match_res = requests.get(detail_url, headers=HEADERS, timeout=10)
                    
                    if match_res.status_code == 200:
                        data = match_res.json()
                        timestamp = data["info"]["gameCreation"]
                        participants = data["metadata"]["participants"]
                        
                        # Insert Match Header
                        cursor.execute("""
                            INSERT INTO Matches (match_id, timestamp) 
                            VALUES (%s, %s) ON CONFLICT (match_id) DO NOTHING
                        """, (match_id, timestamp))
                        
                        # Insert all 10 players
                        for p_puuid in participants:
                            cursor.execute("""
                                INSERT INTO Match_Participants (match_id, puuid) 
                                VALUES (%s, %s) ON CONFLICT (match_id, puuid) DO NOTHING
                            """, (match_id, p_puuid))
                        
                        conn.commit()
                        print(f"      [✓] {match_id} saved.")
                    
                    elif match_res.status_code == 429:
                        print("      [!] Rate limit hit. Taking a 30s nap...")
                        time.sleep(30)
                    else:
                        print(f"      [!] Skipping {match_id}: HTTP {match_res.status_code}")

                except Exception as match_err:
                    print(f"      [!] Critical error on match {match_id}: {match_err}")
                    continue # Keep moving to the next match

        except Exception as player_err:
            print(f"   [!] Error processing player {riot_id}: {player_err}")
            continue # Keep moving to the next player

    cursor.close()
    conn.close()
    print("\n--- Massive Crawl Cycle Finished ---")

if __name__ == "__main__":
    process_incremental_load()