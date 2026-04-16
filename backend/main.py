from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import urllib.parse
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv, find_dotenv
import time

# --- CONFIGURATION ---
load_dotenv(find_dotenv(), override=True)
API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

REGION = "europe"
PLATFORM = "euw1" 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

@app.get("/api/player/{game_name}/{tag_line}")
def get_player_data(game_name: str, tag_line: str):
    # 1. Get Searcher Info
    safe_name = urllib.parse.quote(game_name.strip())
    safe_tag = urllib.parse.quote(tag_line.strip())
    
    acc_url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
    acc_res = requests.get(acc_url, headers=HEADERS)
    
    if acc_res.status_code != 200:
        raise HTTPException(status_code=acc_res.status_code, detail="Player not found.")
        
    target_puuid = acc_res.json()['puuid']

    # 2. Check for Active Game
    spec_url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{target_puuid}"
    spec_res = requests.get(spec_url, headers=HEADERS)
    
    if spec_res.status_code == 200:
        game_data = spec_res.json()
        participants = game_data['participants']
        
        participant_puuids = [p.get('puuid').strip() for p in participants if p.get('puuid')]
        participant_names = [p.get('riotId').strip() for p in participants if p.get('riotId')]

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Dual-match search
        query = "SELECT puuid, pro_id, riot_id FROM Accounts WHERE puuid = ANY(%s) OR riot_id = ANY(%s)"
        cursor.execute(query, (participant_puuids, participant_names))
        found_pros_db = cursor.fetchall()
        
        pro_details = []
        print(f"\n✅ Found {len(found_pros_db)} pro accounts in this lobby.")

        for pro_puuid_db, pro_id, pro_riot_id_db in found_pros_db:
            # Match back to live participant
            p_match = next((p for p in participants if p.get('puuid') == pro_puuid_db or p.get('riotId') == pro_riot_id_db), None)
            if not p_match: continue
            
            champ_id = p_match.get('championId', 0)
            live_puuid = p_match.get('puuid') # This is the "Fresh" Platform PUUID

            cursor.execute("SELECT name FROM Pros WHERE pro_id = %s", (pro_id,))
            pro_name = cursor.fetchone()[0]

            # Get all accounts for this pro
            cursor.execute("SELECT puuid, riot_id FROM Accounts WHERE pro_id = %s", (pro_id,))
            all_accounts = cursor.fetchall()
            
            total_mastery = 0
            print(f"📊 {pro_name} (Champ {champ_id}):")
            
            for acc_puuid_db, acc_riot_id in all_accounts:
                time.sleep(0.05)
                
                # IMPORTANT: If this is the account they are CURRENTLY playing on,
                # use the live_puuid from the spectator API instead of the DB puuid.
                puuid_to_check = live_puuid if acc_riot_id == p_match.get('riotId') else acc_puuid_db
                
                m_url = f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid_to_check.strip()}/by-champion/{champ_id}"
                m_res = requests.get(m_url, headers=HEADERS)
                
                if m_res.status_code == 200:
                    pts = m_res.json().get('championPoints', 0)
                    total_mastery += pts
                    print(f"   + {pts} pts from {acc_riot_id}")
                else:
                    # If it fails, try the other PUUID just in case
                    alt_puuid = acc_puuid_db if puuid_to_check == live_puuid else live_puuid
                    m_res_alt = requests.get(f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{alt_puuid.strip()}/by-champion/{champ_id}", headers=HEADERS)
                    if m_res_alt.status_code == 200:
                        pts = m_res_alt.json().get('championPoints', 0)
                        total_mastery += pts
                        print(f"   + {pts} pts from {acc_riot_id} (via alt ID)")

            pro_details.append({
                "pro_name": pro_name,
                "playing_as_account": p_match.get('riotId', pro_riot_id_db),
                "champion_id": champ_id,
                "true_combined_mastery": total_mastery
            })

        cursor.close()
        conn.close()

        return {
            "status": "live",
            "searched_player": f"{game_name}#{tag_line}",
            "pros_in_game": pro_details
        }

    return {"status": "history", "searched_player": f"{game_name}#{tag_line}", "history": []}