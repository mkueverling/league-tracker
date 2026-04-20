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

    # 1. Players Table (The 3-Tier Master Record)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            known_name VARCHAR(100),
            real_name VARCHAR(100),
            nationality VARCHAR(100),
            role VARCHAR(50),
            team VARCHAR(100),
            birthday DATE,
            signature_champions VARCHAR(50)[],
            profile_image_url VARCHAR(255),
            twitch_url VARCHAR(255),
            twitter_url VARCHAR(255),
            youtube_url VARCHAR(255),
            mantra VARCHAR(255),
            is_pro BOOLEAN DEFAULT FALSE,
            is_creator BOOLEAN DEFAULT FALSE
        );
    """)

    # 2. Accounts Table (The Smurfs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            puuid VARCHAR(100) PRIMARY KEY,
            player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
            riot_id VARCHAR(100) NOT NULL,
            rank VARCHAR(50),
            lp INTEGER,
            ladder_rank INTEGER,
            last_checked TIMESTAMP WITHOUT TIME ZONE
        );
    """)

    # 3. Account Mastery Table (The True Mastery Aggregator)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_mastery (
            puuid VARCHAR(100) REFERENCES accounts(puuid) ON DELETE CASCADE,
            champion_id INTEGER NOT NULL,
            mastery_points BIGINT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (puuid, champion_id)
        );
    """)

    # 4. Matches Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id VARCHAR(50) PRIMARY KEY,
            timestamp BIGINT NOT NULL
        );
    """)

    # 5. Match Participants Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_participants (
            match_id VARCHAR(50) REFERENCES matches(match_id) ON DELETE CASCADE,
            puuid VARCHAR(100),
            win BOOLEAN,
            PRIMARY KEY (match_id, puuid)
        );
    """)

    # 6. Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mp_puuid ON match_participants(puuid);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON matches(timestamp DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mastery_champ ON account_mastery(champion_id);")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("PostgreSQL Schema Initialized successfully.")

if __name__ == "__main__":
    initialize_postgres_schema()