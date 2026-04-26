import os
import requests
import time
import psycopg2
import sys
import argparse
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
REGION = "europe"

def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD")
        )
    except Exception as e:
        print(f"[!] Could not connect to database: {e}")
        sys.exit(1)

def safe_api_call(url):
    """Handles standard rate limiting and potential 429s from Riot."""
    while True:
        res = requests.get(url, headers=HEADERS)
        
        # Riot's hard rate limits: 20 req/sec, 100 req/2min. 
        # 1.2s delay guarantees we never breach the 2-minute limit.
        time.sleep(1.2) 
        
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", 5))
            print(f" [!] Rate limited by Riot. Sleeping for {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f" [!] API Error {res.status_code} on {url}")
            return None

def run_manual_miner(target_puuid):
    print(f"=== Manual Miner Started for PUUID: {target_puuid[:8]}... ===")
    
    # Ask if we want to bypass the high watermark to get older games
    deep_scan_input = input("Do a Deep Scan for older games? (y/n): ").strip().lower()
    deep_scan = deep_scan_input == 'y'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    start_index = 0
    chunk_size = 100 # Riot's maximum allowed count per request
    total_saved = 0

    try:
        while True:
            print(f"\n[*] Fetching matches {start_index} to {start_index + chunk_size}...")
            
            # 1. Fetch match IDs in bulk
            url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{target_puuid}/ids?start={start_index}&count={chunk_size}"
            match_ids = safe_api_call(url)
            
            if not match_ids:
                print("\n[✓] Reached the end of the player's accessible history.")
                print(f"=== Finished. Successfully mined {total_saved} new matches. ===")
                break
                
            # 2. Iterate through the fetched matches
            for match_id in match_ids:
                
                # CHECK DATABASE FOR DUPLICATES
                cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
                if cursor.fetchone():
                    if deep_scan:
                        print(f" -> [SKIPPED] {match_id} (Already in DB)")
                        continue # Keep searching older games
                    else:
                        print(f"\n[✓] High Watermark Reached: Match {match_id} is already in the database.")
                        print(f"=== Finished. Successfully mined {total_saved} new matches. ===")
                        return # Stop the script completely
                    
                # Fetch match details
                print(f" -> Fetching details for {match_id}...")
                match_data = safe_api_call(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}")
                
                if not match_data:
                    continue # Skip this match if API failed
                    
                timestamp = match_data['info']['gameCreation']
                
                # Save Match ID
                cursor.execute("INSERT INTO matches (match_id, timestamp) VALUES (%s, %s) ON CONFLICT DO NOTHING", (match_id, timestamp))
                
                # Save all 10 participants
                for p in match_data['info']['participants']:
                    cursor.execute("""
                        INSERT INTO match_participants (match_id, puuid, team_id, win) 
                        VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                    """, (match_id, p['puuid'], p['teamId'], p['win']))
                    
                conn.commit()
                total_saved += 1
                
            # Advance to the next pagination chunk
            start_index += chunk_size

    except Exception as e:
        print(f"\n[!] Miner Error: {e}")
        conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch full match history for a specific Riot PUUID.")
    parser.add_argument("puuid", nargs='?', help="The PUUID of the player to mine.")
    args = parser.parse_args()

    if args.puuid:
        run_manual_miner(args.puuid)
    else:
        print("Please provide a PUUID.")
        target = input("PUUID: ").strip()
        if target:
            run_manual_miner(target)