from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, os, urllib.parse, psycopg2, time
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)
API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
REGION, PLATFORM = "europe", "euw1"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), 
        database=os.getenv("DB_NAME"), 
        user=os.getenv("DB_USER"), 
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=5
    )

def get_rank_info(puuid):
    if not puuid: return "unranked"
    try:
        url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        res = requests.get(url, headers=HEADERS, timeout=3)
        if res.status_code == 200:
            data = res.json()
            for entry in data:
                if entry.get('queueType') == 'RANKED_SOLO_5x5':
                    return entry.get('tier', 'unranked').lower()
    except Exception: pass
    return "unranked"

def get_streak_tag(cursor, puuid):
    if not puuid: return None
    try:
        cursor.execute("""
            SELECT mp.win FROM Match_Participants mp 
            JOIN Matches m ON mp.match_id = m.match_id 
            WHERE mp.puuid = %s 
            ORDER BY m.timestamp DESC LIMIT 10
        """, (puuid,))
        history = cursor.fetchall()
        if not history: return None
        
        wins, losses = 0, 0
        stype = "win" if history[0]['win'] else "loss"
        for g in history:
            if stype == "win" and g['win']: wins += 1
            elif stype == "loss" and not g['win']: losses += 1
            else: break
        
        tags = {7: "Winners Queue", 5: "On Fire", 3: "Winning"} if stype == "win" else {7: "Losers Queue", 5: "Tilted", 3: "Unlucky"}
        for threshold, label in tags.items():
            if (wins if stype == "win" else losses) >= threshold: return label
    except Exception: pass
    return None

@app.get("/api/player/{name}/{tag}")
def get_player(name: str, tag: str):
    conn = None
    try:
        acc_url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
        acc_res = requests.get(acc_url, headers=HEADERS, timeout=5)
        if acc_res.status_code != 200:
            raise HTTPException(status_code=404, detail="Player not found")
        target_puuid = acc_res.json().get('puuid')

        spec_url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{target_puuid}"
        spec_res = requests.get(spec_url, headers=HEADERS, timeout=5)
        if spec_res.status_code != 200:
            return {"status": "history"}

        game_data = spec_res.json()
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        searcher_team_id = next((p['teamId'] for p in game_data['participants'] if p.get('puuid') == target_puuid), 100)
        searcher_tag = get_streak_tag(cursor, target_puuid)
        
        allies, enemies = [], []
        ally_m_total, enemy_m_total = 0, 0
        ally_streaks, enemy_streaks = 0, 0

        for p in game_data['participants']:
            raw_p_puuid = p.get('puuid')
            puuid = raw_p_puuid.strip() if raw_p_puuid else None
            riot_id = p.get('riotId', 'Unknown').strip()
            champ_id = p.get('championId', 0)
            
            is_streamer = puuid is None
            pro_entry, cur_mast, tot_mast, tag_disp, rank_tier = None, 0, 0, None, "unranked"

            if not is_streamer:
                # 1. Identify the Pro by current account
                cursor.execute("""
                    SELECT p.pro_id, p.name 
                    FROM Pros p 
                    JOIN Accounts a ON p.pro_id = a.pro_id 
                    WHERE a.puuid = %s OR a.riot_id = %s 
                    LIMIT 1
                """, (puuid, riot_id))
                pro_entry = cursor.fetchone()
                
                rank_tier = get_rank_info(puuid)
                p_streak = get_streak_tag(cursor, puuid)

                # 2. Get Mastery for Current Account
                m_res = requests.get(f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champ_id}", headers=HEADERS, timeout=3)
                if m_res.status_code == 200: 
                    cur_mast = m_res.json().get('championPoints', 0)
                
                tot_mast = cur_mast # Start with current account points
                
                # 3. If it's a Pro, find ALL linked accounts and sum them
                if pro_entry:
                    cursor.execute("SELECT puuid FROM Accounts WHERE pro_id = %s", (pro_entry['pro_id'],))
                    all_linked_puuids = [row['puuid'].strip() for row in cursor.fetchall()]
                    
                    for s_puuid in all_linked_puuids:
                        # Skip the one we already checked
                        if s_puuid == puuid:
                            continue
                        
                        time.sleep(0.05) # Rate Limit Safety
                        m_res_alt = requests.get(f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{s_puuid}/by-champion/{champ_id}", headers=HEADERS, timeout=3)
                        if m_res_alt.status_code == 200:
                            tot_mast += m_res_alt.json().get('championPoints', 0)
                
                tag_disp = tag_disp or (searcher_tag if puuid == target_puuid else p_streak)
                if p_streak == "Winners Queue" and tot_mast > 200000: tag_disp = "YOU'RE COOKED"
                
                if p['teamId'] == searcher_team_id:
                    ally_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: ally_streaks += 1
                else:
                    enemy_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: enemy_streaks += 1

            p_payload = {
                "puuid": puuid, "riotId": riot_id if not is_streamer else "STREAMER MODE",
                "is_streamer": is_streamer, "championId": champ_id, "is_pro": pro_entry is not None,
                "pro_name": pro_entry['name'] if pro_entry else None, "rank": rank_tier,
                "current_mastery": cur_mast, "total_mastery": tot_mast, "tag": tag_disp,
                "side": "ally" if p['teamId'] == searcher_team_id else "enemy"
            }
            if p['teamId'] == searcher_team_id: allies.append(p_payload)
            else: enemies.append(p_payload)

        ff_angle = (enemy_m_total >= (ally_m_total * 2) and enemy_streaks >= (ally_streaks * 2) and enemy_streaks > 0)
        return {"status": "live", "allies": allies, "enemies": enemies, "ff_angle": ff_angle}

    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()