import os
import requests
import time
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

# Ranked endpoints require PLATFORM routing (euw1), not regional (europe)
PLATFORM = "euw1" 

def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD")
        )
    except Exception as e:
        print(f"[!] Could not connect to database: {e}")
        sys.exit(1)

def get_apex_ladder():
    """Fetches and combines Challenger, GM, and Master ladders, sorting by LP."""
    tiers = ['challengerleagues', 'grandmasterleagues', 'masterleagues']
    all_entries = []
    
    for tier in tiers:
        url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/{tier}/by-queue/RANKED_SOLO_5x5"
        res = requests.get(url, headers=HEADERS)
        time.sleep(1.2) # Rate limit safety
        
        if res.status_code == 200:
            data = res.json()
            all_entries.extend(data.get('entries', []))
            print(f" [✓] Fetched {tier} ({len(data.get('entries', []))} players)")
        else:
            print(f" [!] Failed to fetch {tier}: HTTP {res.status_code}")
            
    # Sort all apex players by League Points (descending)
    all_entries.sort(key=lambda x: x['leaguePoints'], reverse=True)
    return all_entries

def update_leaderboard():
    print("=== Fetching Apex Ladders ===")
    ladder = get_apex_ladder()
    
    # Create a blazing fast dictionary lookup using PUUID directly!
    ladder_map = {entry['puuid']: index + 1 for index, entry in enumerate(ladder)}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print("\n=== Updating Tracked Accounts in apex_ladder ===")
        
        cursor.execute("SELECT puuid, riot_id FROM accounts")
        accounts = cursor.fetchall()
        
        for puuid, riot_id in accounts:
            # 1. Look up their rank instantly without an extra API call
            rank = ladder_map.get(puuid)
            
            if rank:
                # 2. Insert or update their rank in the apex_ladder table
                cursor.execute("""
                    INSERT INTO apex_ladder (puuid, rank) 
                    VALUES (%s, %s) 
                    ON CONFLICT (puuid) DO UPDATE SET rank = EXCLUDED.rank
                """, (puuid, rank))
                print(f" [↑] {riot_id} is currently Rank #{rank}")
            else:
                # 3. They fell out of Master+ (or haven't reached it). Remove them.
                cursor.execute("DELETE FROM apex_ladder WHERE puuid = %s", (puuid,))
                print(f" [-] {riot_id} is not in Master+")
                
        conn.commit()
        print("\n=== Leaderboard Update Complete ===")
        
    except Exception as e:
        print(f"\n[!] Database Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_leaderboard()