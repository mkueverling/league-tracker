from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv
import time

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("RIOT_API_KEY")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

import time  # add this at the top of the file

def query_postgres(puuid):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()

    thirty_days_ago_ms = int(time.time() * 1000) - (30 * 24 * 60 * 60 * 1000)
    
    query = '''
        SELECT 
            m.match_id, 
            m.timestamp,
            p.name, 
            p.twitch_url, 
            p.twitter_url, 
            p.youtube_url, 
            a.riot_id
        FROM Match_Participants mp_user
        JOIN Match_Participants mp_pro ON mp_user.match_id = mp_pro.match_id
        JOIN Matches m ON mp_user.match_id = m.match_id
        JOIN Accounts a ON mp_pro.puuid = a.puuid
        JOIN Pros p ON a.pro_id = p.pro_id
        WHERE mp_user.puuid = %s 
          AND mp_user.puuid != mp_pro.puuid
          AND m.timestamp >= %s
        ORDER BY m.timestamp DESC
    '''
    cursor.execute(query, (puuid, thirty_days_ago_ms))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    grouped = {}
    for row in results:
        match_id, timestamp, pro_name, twitch, twitter, youtube, pro_riot_id = row
        
        if match_id not in grouped:
            grouped[match_id] = {
                "match_id": match_id,
                "timestamp": timestamp,
                "stats_url": f"https://www.leagueofgraphs.com/match/euw/{match_id.split('_')[1]}",
                "pros": []
            }
        
        grouped[match_id]["pros"].append({
            "pro_name": pro_name,
            "twitch": twitch,
            "twitter": twitter,
            "youtube": youtube,
            "pro_riot_id": pro_riot_id
        })
    
    return list(grouped.values())

@app.get("/api/search")
async def search_player(gameName: str, tagLine: str):
    headers = {"X-Riot-Token": API_KEY}
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Riot ID not found")
        
    user_puuid = response.json().get('puuid')
    matched_games = query_postgres(user_puuid)
    
    return {
        "matches_found": len(matched_games),
        "matches": matched_games
    }