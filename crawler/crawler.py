import requests
import time
import sys
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# 1. Bulletproof path resolution (Same as sync.py)
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
    """Finds the most recent match timestamp for a specific PUUID to avoid duplicates."""
    cursor.execute("""
        SELECT MAX(m.timestamp) 
        FROM Matches m
        JOIN Match_Participants mp ON m.match_id = mp.match_id
        WHERE mp.puuid = %s
    """, (puuid,))
    result = cursor.fetchone()[0]
    
    if result:
        # Convert milliseconds to seconds for the Riot API and add 1 second
        return int(result / 1000) + 1 
    return None

def process_incremental_load():
    print(f"DEBUG: Using API Key starting with -> {str(API_KEY)[:10]}...")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all active pro accounts from the DB
    cursor.execute("SELECT puuid, riot_id FROM Accounts")
    accounts = cursor.fetchall()

    for puuid, riot_id in accounts:
        print(f"\n--- Crawling matches for {riot_id} ---")
        
        # Check the watermark
        last_timestamp = get_high_water_mark(cursor, puuid)
        
        # Build the initial URL
        url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=100"
        
        if last_timestamp:
            print(f"Incremental Load: Fetching matches after epoch {last_timestamp}")
            url += f"&startTime={last_timestamp}"
        else:
            print("Historical Load: New account detected. Fetching last 100 matches.")

        # Fetch Match IDs
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch match list: HTTP {response.status_code}")
            continue
            
        match_ids = response.json()
        print(f"Found {len(match_ids)} new matches to process.")
        
        if not match_ids:
            continue

        # Fetch Details and Insert into PostgreSQL
        for match_id in match_ids:
            time.sleep(1.2) # Rate limit pacing
            
            detail_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_res = requests.get(detail_url, headers=HEADERS)
            
            if match_res.status_code == 200:
                data = match_res.json()
                timestamp = data["info"]["gameCreation"]
                participants = data["metadata"]["participants"]
                
                # Insert the Match (ON CONFLICT DO NOTHING prevents crashing if it already exists)
                cursor.execute("""
                    INSERT INTO Matches (match_id, timestamp) 
                    VALUES (%s, %s) ON CONFLICT (match_id) DO NOTHING
                """, (match_id, timestamp))
                
                # Insert all 10 players in that match
                for p in participants:
                    cursor.execute("""
                        INSERT INTO Match_Participants (match_id, puuid) 
                        VALUES (%s, %s) ON CONFLICT (match_id, puuid) DO NOTHING
                    """, (match_id, p))
                
                conn.commit()
                print(f"Inserted: {match_id}")
            else:
                print(f"Failed match {match_id}: HTTP {match_res.status_code}")

    cursor.close()
    conn.close()
    print("\nCrawler run complete.")

if __name__ == "__main__":
    process_incremental_load()