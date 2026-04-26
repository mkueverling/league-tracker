import os
import requests
import time
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

# Mastery endpoints require PLATFORM routing (euw1), not regional (europe)
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

def sync_missing_masteries():
    print("=== True Mastery Sync Started ===")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Find all accounts that have ZERO entries in the account_mastery table
        print("[*] Scanning database for accounts missing mastery data...")
        cursor.execute("""
            SELECT puuid, riot_id 
            FROM accounts a
            WHERE NOT EXISTS (
                SELECT 1 FROM account_mastery am WHERE am.puuid = a.puuid
            )
        """)
        
        missing_accounts = cursor.fetchall()
        
        if not missing_accounts:
            print(" [✓] All tracked accounts already have mastery data synced!")
            return
            
        print(f"[*] Found {len(missing_accounts)} accounts needing mastery sync.\n")
        
        for puuid, riot_id in missing_accounts:
            # 2. Call the Champion Mastery V4 endpoint
            url = f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
            res = requests.get(url, headers=HEADERS)
            time.sleep(1.2) # Rate limit safety
            
            if res.status_code == 200:
                masteries = res.json()
                
                # 3. Loop and save every champion the player has ever played
                for mastery in masteries:
                    champ_id = mastery['championId']
                    points = mastery['championPoints']
                    
                    cursor.execute("""
                        INSERT INTO account_mastery (puuid, champion_id, mastery_points, last_updated)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (puuid, champion_id) DO UPDATE SET 
                            mastery_points = EXCLUDED.mastery_points,
                            last_updated = NOW()
                    """, (puuid, champ_id, points))
                
                conn.commit()
                print(f" [✓] Synced {len(masteries)} champions for {riot_id}")
            else:
                print(f" [!] Failed to fetch mastery for {riot_id} (HTTP {res.status_code})")
                
        print("\n=== True Mastery Sync Complete ===")
        
    except Exception as e:
        print(f"\n[!] Database Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    sync_missing_masteries()