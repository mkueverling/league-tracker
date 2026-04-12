from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import httpx
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
API_KEY = os.getenv("RIOT_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

def query_postgres(puuid):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = conn.cursor()
    
    # Notice the syntax change from ? to %s for Postgres
    query = '''
        SELECT m.match_id
        FROM Match_Participants mp_user
        JOIN Matches m ON mp_user.match_id = m.match_id
        JOIN Match_Participants mp_pro ON m.match_id = mp_pro.match_id
        WHERE mp_user.puuid = %s AND mp_user.puuid != mp_pro.puuid
    '''
    cursor.execute(query, (puuid,))
    matches = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return [row[0] for row in matches]

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
        "pro_details": {
            "name": "Pro Player", # We will dynamically query this via JOINs later
            "riot_id": "Hidden#EUW",
            "twitch": "https://twitch.tv",
            "twitter": "https://x.com"
        },
        "matches": [
            {"match_id": m, "stats_url": f"https://www.leagueofgraphs.com/match/euw/{m.split('_')[1]}"}
            for m in matched_games
        ]
    }