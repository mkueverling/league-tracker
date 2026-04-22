import os
import requests
import time
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
PLATFORM = "euw1" 

def sync_masteries():
    print("=== Syncing True Mastery for all accounts ===")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()

    # 1. Ensure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_mastery (
            puuid VARCHAR(100),
            champion_id INTEGER,
            mastery_points BIGINT,
            PRIMARY KEY (puuid, champion_id)
        )
    """)
    conn.commit()

    # 2. Get all known accounts
    cursor.execute("SELECT puuid, riot_id FROM accounts")
    accounts = cursor.fetchall()
    
    print(f"Found {len(accounts)} accounts. Fetching data from Riot...")

    for puuid, riot_id in accounts:
        try:
            url = f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
            res = requests.get(url, headers=HEADERS, timeout=10)

            if res.status_code == 429:
                print(" [!] Rate limited. Sleeping for 15 seconds...")
                time.sleep(15)
                res = requests.get(url, headers=HEADERS, timeout=10) # Simple retry
                
            if res.status_code == 200:
                masteries = res.json()
                
                # Prepare data for lightning-fast batch insert
                insert_data = [
                    (puuid, m['championId'], m['championPoints']) 
                    for m in masteries
                ]
                
                if insert_data:
                    execute_batch(cursor, """
                        INSERT INTO account_mastery (puuid, champion_id, mastery_points)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (puuid, champion_id) DO UPDATE SET
                            mastery_points = EXCLUDED.mastery_points
                    """, insert_data)
                    conn.commit()
                    print(f" [✓] Updated: {riot_id} ({len(insert_data)} champions)")
            else:
                print(f" [x] Failed to fetch {riot_id}: HTTP {res.status_code}")
            
            # Respect Riot's rate limits
            time.sleep(1.2) 
            
        except Exception as e:
            print(f" [!] Error syncing {riot_id}: {e}")

    cursor.close()
    conn.close()
    print("=== Sync Complete ===")

if __name__ == "__main__":
    sync_masteries()