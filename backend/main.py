from fastapi import FastAPI, HTTPException
import requests
import os
import urllib.parse
import psycopg2
import psycopg2.extras # Added to return SQL results as clean dictionaries
from dotenv import load_dotenv, find_dotenv

# --- CONFIGURATION ---
load_dotenv(find_dotenv(), override=True)
API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

# Riot Account API uses regions (europe), but Live Games/Mastery use platforms (euw1)
REGION = "europe"
PLATFORM = "euw1" 

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

@app.get("/api/player/{game_name}/{tag_line}")
def get_player_data(game_name: str, tag_line: str):
    # 1. Safely URL-Encode the name
    safe_name = urllib.parse.quote(game_name.strip())
    safe_tag = urllib.parse.quote(tag_line.strip())
    
    # 2. Get the Searcher's PUUID
    acc_url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
    acc_res = requests.get(acc_url, headers=HEADERS)
    
    if acc_res.status_code == 404:
        raise HTTPException(status_code=404, detail="Player not found in Riot system.")
    elif acc_res.status_code != 200:
        raise HTTPException(status_code=acc_res.status_code, detail="Error fetching account.")
        
    target_puuid = acc_res.json()['puuid']

    # 3. Check for an Active Game
    spec_url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{target_puuid}"
    spec_res = requests.get(spec_url, headers=HEADERS)
    
    # ==========================================
    # BRANCH A: THE PLAYER IS IN A LIVE GAME
    # ==========================================
    if spec_res.status_code == 200:
        game_data = spec_res.json()

        # Fetch Rank/LP
        league_url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{target_puuid}"
        league_res = requests.get(league_url, headers=HEADERS)
        rank_data = league_res.json() if league_res.status_code == 200 else []

        # Extract the 10 players
        participants = game_data['participants']
        participant_puuids = [p['puuid'] for p in participants]

        # Database Check: Are any of these 10 players PROS?
        conn = get_db_connection()
        cursor = conn.cursor()
        
        format_strings = ','.join(['%s'] * len(participant_puuids))
        cursor.execute(f"SELECT puuid, pro_id, riot_id FROM Accounts WHERE puuid IN ({format_strings})", tuple(participant_puuids))
        found_pros = cursor.fetchall()

        pro_details = []
        for pro_puuid, pro_id, pro_riot_id in found_pros:
            champ_id = next(p['championId'] for p in participants if p['puuid'] == pro_puuid)
            
            cursor.execute("SELECT name FROM Pros WHERE pro_id = %s", (pro_id,))
            pro_name = cursor.fetchone()[0]
            
            # The Mastery Aggregator
            cursor.execute("SELECT puuid FROM Accounts WHERE pro_id = %s", (pro_id,))
            all_smurfs = cursor.fetchall()
            
            total_mastery = 0
            for (smurf_puuid,) in all_smurfs:
                mast_url = f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{smurf_puuid}/by-champion/{champ_id}"
                mast_res = requests.get(mast_url, headers=HEADERS)
                if mast_res.status_code == 200:
                    total_mastery += mast_res.json().get('championPoints', 0)
                    
            pro_details.append({
                "pro_name": pro_name,
                "playing_as_account": pro_riot_id,
                "champion_id": champ_id,
                "true_combined_mastery": total_mastery
            })

        cursor.close()
        conn.close()

        return {
            "status": "live",
            "searched_player": f"{game_name}#{tag_line}",
            "game_mode": game_data.get('gameMode'),
            "rank_data": rank_data,
            "pros_in_game": pro_details
        }

    # ==========================================
    # BRANCH B: THE PLAYER IS NOT IN A GAME (HISTORY)
    # ==========================================
    elif spec_res.status_code == 404:
        conn = get_db_connection()
        # RealDictCursor makes the SQL output look exactly like nice JSON objects
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Step A: Find the last 10 matches this specific player was in
        cursor.execute("""
            SELECT m.match_id, m.timestamp
            FROM Matches m
            JOIN Match_Participants mp ON m.match_id = mp.match_id
            WHERE mp.puuid = %s
            ORDER BY m.timestamp DESC
            LIMIT 10;
        """, (target_puuid,))
        recent_matches = cursor.fetchall()

        if not recent_matches:
            cursor.close()
            conn.close()
            return {
                "status": "history",
                "searched_player": f"{game_name}#{tag_line}",
                "message": "No matches found with pros in our database.",
                "history": []
            }

        # Step B: Look at those specific matches and see which Pros were in them
        match_ids = [m['match_id'] for m in recent_matches]
        format_strings = ','.join(['%s'] * len(match_ids))
        
        cursor.execute(f"""
            SELECT mp.match_id, p.name AS pro_name, a.riot_id AS pro_account
            FROM Match_Participants mp
            JOIN Accounts a ON mp.puuid = a.puuid
            JOIN Pros p ON a.pro_id = p.pro_id
            WHERE mp.match_id IN ({format_strings})
        """, tuple(match_ids))
        
        pros_in_matches = cursor.fetchall()

        cursor.close()
        conn.close()

        # Step C: Bundle it together nicely for the frontend
        history_payload = []
        for match in recent_matches:
            match_id = match['match_id']
            # Find all pros that share this match_id
            pros_here = [
                {"pro_name": p['pro_name'], "account": p['pro_account']} 
                for p in pros_in_matches if p['match_id'] == match_id
            ]
            
            history_payload.append({
                "match_id": match_id,
                "timestamp": match['timestamp'],
                "pros_in_game": pros_here
            })

        return {
            "status": "history",
            "searched_player": f"{game_name}#{tag_line}",
            "history": history_payload
        }

    else:
        raise HTTPException(status_code=spec_res.status_code, detail="Error checking live game status.")