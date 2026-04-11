import sqlite3
import json
import os

def initialize_db(db_name="league_tracker.db"):
    # Connects to the file (creates it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # 1. Enable WAL mode to prevent database locking issues later
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # 2. Create the normalized schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Matches (
            match_id TEXT PRIMARY KEY,
            timestamp INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Match_Participants (
            match_id TEXT,
            puuid TEXT,
            FOREIGN KEY(match_id) REFERENCES Matches(match_id),
            UNIQUE(match_id, puuid)
        )
    ''')
    
    # 3. Create the B-Tree Index for millisecond lookup speeds
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_participant_puuid 
        ON Match_Participants(puuid)
    ''')
    
    conn.commit()
    return conn

def load_match_data(conn, json_filename="sample_match.json"):
    if not os.path.exists(json_filename):
        print(f"Error: {json_filename} not found.")
        return

    with open(json_filename, "r") as f:
        data = json.load(f)
        
    # Extract the exact fields we need
    match_id = data["metadata"]["matchId"]
    participants = data["metadata"]["participants"]
    timestamp = data["info"]["gameCreation"]
    
    cursor = conn.cursor()
    
    print(f"Loading Match: {match_id}")
    
    # Insert into Matches table
    # We use INSERT OR IGNORE so the crawler doesn't crash if it accidentally fetches the same game twice
    cursor.execute('''
        INSERT OR IGNORE INTO Matches (match_id, timestamp) 
        VALUES (?, ?)
    ''', (match_id, timestamp))
    
    # Insert the 10 participants into the junction table
    for puuid in participants:
        cursor.execute('''
            INSERT OR IGNORE INTO Match_Participants (match_id, puuid) 
            VALUES (?, ?)
        ''', (match_id, puuid))
        
    conn.commit()
    print("Load complete. 1 Match and 10 Participant records inserted.")

def verify_data(conn):
    # A quick read-query to prove the data is physically on the disk
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Matches")
    match_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Match_Participants")
    participant_count = cursor.fetchone()[0]
    
    print(f"\n--- Database State ---")
    print(f"Total Matches: {match_count}")
    print(f"Total Participants Mapped: {participant_count}")

if __name__ == "__main__":
    db_connection = initialize_db()
    load_match_data(db_connection)
    verify_data(db_connection)
    db_connection.close()