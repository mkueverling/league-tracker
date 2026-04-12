import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# Bulletproof path resolution:
# 1. Gets the exact location of database.py
# 2. Goes up one level to the root 'league-tracker' folder
# 3. Finds the .env file exactly there
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

# ... (keep the rest of the file exactly the same)

def initialize_postgres_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Dimension Tables (Updated with Social Links)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Pros (
            pro_id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            twitch_url VARCHAR(255),
            twitter_url VARCHAR(255),
            youtube_url VARCHAR(255)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Accounts (
            puuid VARCHAR(100) PRIMARY KEY,
            pro_id INTEGER REFERENCES Pros(pro_id),
            riot_id VARCHAR(100) NOT NULL
        );
    """)

    # 2. Fact Tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Matches (
            match_id VARCHAR(50) PRIMARY KEY,
            timestamp BIGINT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Match_Participants (
            match_id VARCHAR(50) REFERENCES Matches(match_id),
            puuid VARCHAR(100),
            PRIMARY KEY (match_id, puuid)
        );
    """)

    # 3. Indexing for read-heavy frontend search speeds
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mp_puuid ON Match_Participants(puuid);")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("PostgreSQL Schema Initialized. Social columns added.")

if __name__ == "__main__":
    initialize_postgres_schema()