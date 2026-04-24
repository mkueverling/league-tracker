import os
import requests
import time
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
REGION = "europe"

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD")
    )

def run_miner():
    print("=== ProTracker Background Miner Started ===")
    while True:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 1. Grab the user who hasn't been updated in the longest time
            cursor.execute("""
                SELECT puuid FROM tracked_users 
                ORDER BY last_updated ASC LIMIT 1;
            """)
            row = cursor.fetchone()
            
            if not row:
                print("No tracked users in queue. Sleeping for 10 seconds...")
                time.sleep(10)
                continue
                
            target_puuid = row[0]
            print(f"\n[Miner] Checking matches for: {target_puuid}")
            
            # 2. Fetch their last 5 matches
            url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{target_puuid}/ids?start=0&count=5"
            res = requests.get(url, headers=HEADERS)
            time.sleep(1.2) # Rate limit safety
            
            if res.status_code == 200:
                match_ids = res.json()
                for match_id in match_ids:
                    # Skip if we already saved this match
                    cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
                    if cursor.fetchone():
                        continue 
                        
                    # Fetch the match details
                    m_res = requests.get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}", headers=HEADERS)
                    time.sleep(1.2) # Rate limit safety
                    
                    if m_res.status_code == 200:
                        data = m_res.json()
                        timestamp = data['info']['gameCreation']
                        
                        # Save Match ID
                        cursor.execute("INSERT INTO matches (match_id, timestamp) VALUES (%s, %s) ON CONFLICT DO NOTHING", (match_id, timestamp))
                        
                        # Save all 10 participants
                        for p in data['info']['participants']:
                            cursor.execute("""
                                INSERT INTO match_participants (match_id, puuid, team_id, win) 
                                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                            """, (match_id, p['puuid'], p['teamId'], p['win']))
                            
                        conn.commit()
                        print(f"   -> [SAVED] {match_id} (10 participants logged)")
            
            # 3. Put them at the back of the queue
            cursor.execute("UPDATE tracked_users SET last_updated = NOW() WHERE puuid = %s", (target_puuid,))
            conn.commit()
            
        except Exception as e:
            print(f"[!] Miner Error: {e}")
            time.sleep(5)
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    run_miner()