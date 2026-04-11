from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import httpx # Async HTTP client (pip install httpx)
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
API_KEY = os.getenv("RIOT_API_KEY")

app = FastAPI()

# Enforce CORS to allow the frontend on port 3000 to talk to port 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

def query_db(puuid):
    # This executes the parameterized SQL lookup we designed earlier
    conn = sqlite3.connect('../data/league_tracker.db')
    cursor = conn.cursor()
    
    query = '''
        SELECT m.match_id
        FROM Match_Participants mp_user
        JOIN Matches m ON mp_user.match_id = m.match_id
        JOIN Match_Participants mp_pro ON m.match_id = mp_pro.match_id
        WHERE mp_user.puuid = ? AND mp_user.puuid != mp_pro.puuid
    '''
    cursor.execute(query, (puuid,))
    matches = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in matches]

@app.get("/api/search")
async def search_player(gameName: str, tagLine: str):
    # 1. Talk to Riot to get the user's PUUID
    headers = {"X-Riot-Token": API_KEY}
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Riot ID not found")
        
    user_puuid = response.json().get('puuid')
    
    # 2. Query local database
    matched_games = query_db(user_puuid)
    
    # 3. Format and return the payload
    # Note: For this example, Pro details are mocked. In production, you join your Pros table.
    return {
        "matches_found": len(matched_games),
        "pro_details": {
            "name": "Jankos",
            "riot_id": "G2 Jankos#unc2",
            "twitch": "https://twitch.tv/jankos",
            "twitter": "https://x.com/G2Jankos"
        },
        "matches": [
            {"match_id": m, "stats_url": f"https://www.leagueofgraphs.com/match/euw/{m.split('_')[1]}"}
            for m in matched_games
        ]
    }