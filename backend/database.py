import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# Bulletproof path resolution
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def initialize_postgres_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("Initializing PostgreSQL Schema...")

    # 1. Pros Table (The Master Record)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Pros (
            pro_id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            twitch_url VARCHAR(255),
            twitter_url VARCHAR(255),
            youtube_url VARCHAR(255)
        );
    """)

    # 2. Accounts Table (The Smurfs)
    # Linked to Pros. If a pro is deleted, their accounts are removed (CASCADE).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Accounts (
            puuid VARCHAR(100) PRIMARY KEY,
            pro_id INTEGER REFERENCES Pros(pro_id) ON DELETE CASCADE,
            riot_id VARCHAR(100) NOT NULL
        );
    """)

    # 3. Matches Table (The Metadata)
    # Use BIGINT for timestamp to avoid 'NumericValueOutOfRange' (milliseconds)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Matches (
            match_id VARCHAR(50) PRIMARY KEY,
            timestamp BIGINT NOT NULL
        );
    """)

    # 4. Match Participants Table (The Bridge)
    # Stores all 10 players per match.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Match_Participants (
            match_id VARCHAR(50) REFERENCES Matches(match_id) ON DELETE CASCADE,
            puuid VARCHAR(100),
            PRIMARY KEY (match_id, puuid)
        );
    """)

    # 5. Performance Indexes
    # Crucial for fast frontend searches when table reaches 500k+ rows
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mp_puuid ON Match_Participants(puuid);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON Matches(timestamp DESC);")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("PostgreSQL Schema Initialized successfully.")

if __name__ == "__main__":
    initialize_postgres_schema()