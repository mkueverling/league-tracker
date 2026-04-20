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
        host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), 
        user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"), connect_timeout=5
    )

def get_rank_info(puuid):
    if not puuid: return {"tier": "unranked", "lp": 0}
    try:
        url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        res = requests.get(url, headers=HEADERS, timeout=3)
        if res.status_code == 200:
            for entry in res.json():
                if entry.get('queueType') == 'RANKED_SOLO_5x5':
                    return {"tier": entry.get('tier', 'unranked').lower(), "lp": entry.get('leaguePoints', 0)}
    except Exception: pass
    return {"tier": "unranked", "lp": 0}

def get_streak_tag(cursor, puuid):
    if not puuid: return None
    try:
        cursor.execute("""
            SELECT mp.win FROM match_participants mp JOIN matches m ON mp.match_id = m.match_id 
            WHERE mp.puuid = %s ORDER BY m.timestamp DESC LIMIT 10
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
        
        # Explicit Rate Limit check
        if acc_res.status_code == 429: raise HTTPException(status_code=429, detail="Riot API rate limit reached. Please wait 2 minutes.")
        if acc_res.status_code != 200: raise HTTPException(status_code=404, detail="Player not found")
        
        target_puuid = acc_res.json().get('puuid')

        spec_url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{target_puuid}"
        spec_res = requests.get(spec_url, headers=HEADERS, timeout=5)
        
        # Check rate limit on spectator too
        if spec_res.status_code == 429: raise HTTPException(status_code=429, detail="Riot API rate limit reached. Please wait 2 minutes.")
        if spec_res.status_code != 200: return {"status": "history"}

        game_data = spec_res.json()
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        searcher_team_id = next((p['teamId'] for p in game_data['participants'] if p.get('puuid') == target_puuid), 100)
        searcher_tag = get_streak_tag(cursor, target_puuid)
        
        allies, enemies = [], []
        ally_m_total, enemy_m_total, ally_streaks, enemy_streaks = 0, 0, 0, 0

        for p in game_data['participants']:
            puuid = p.get('puuid').strip() if p.get('puuid') else None
            riot_id = p.get('riotId', 'Unknown').strip()
            champ_id = p.get('championId', 0)
            
            is_streamer = puuid is None
            player_entry, cur_mast, tot_mast, tag_disp = None, 0, 0, None
            rank_data = {"tier": "unranked", "lp": 0}
            smurfs_list = []

            is_pro = False
            is_creator = False
            socials_dict = {}

            if not is_streamer:
                cursor.execute("SELECT p.* FROM players p JOIN accounts a ON p.player_id = a.player_id WHERE a.puuid = %s OR a.riot_id = %s LIMIT 1", (puuid, riot_id))
                player_entry = cursor.fetchone()
                rank_data = get_rank_info(puuid)
                p_streak = get_streak_tag(cursor, puuid)

                if player_entry:
                    cursor.execute("SELECT riot_id FROM accounts WHERE player_id = %s AND riot_id != %s", (player_entry['player_id'], riot_id))
                    smurfs_list = [row['riot_id'] for row in cursor.fetchall() if row['riot_id']]

                    t_twitch = player_entry.get('twitch_url') or player_entry.get('twitch')
                    t_twitter = player_entry.get('twitter_url') or player_entry.get('twitter')
                    t_youtube = player_entry.get('youtube_url') or player_entry.get('youtube')

                    if t_twitch and str(t_twitch).strip() and str(t_twitch).strip().lower() != "none": socials_dict["Twitch"] = str(t_twitch).strip()
                    if t_twitter and str(t_twitter).strip() and str(t_twitter).strip().lower() != "none": socials_dict["Twitter"] = str(t_twitter).strip()
                    if t_youtube and str(t_youtube).strip() and str(t_youtube).strip().lower() != "none": socials_dict["YouTube"] = str(t_youtube).strip()

                    is_pro = bool(player_entry.get('is_pro'))
                    is_creator = bool(player_entry.get('is_creator')) or (len(socials_dict) > 0)
                    
                    if not is_pro and not is_creator:
                        is_pro = True

                # Pacer for the mastery loop to avoid 20 requests/1sec limit
                time.sleep(0.1) 
                m_res = requests.get(f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champ_id}", headers=HEADERS, timeout=3)
                
                if m_res.status_code == 429:
                    cur_mast = 0 # Skip cleanly if rate limited
                elif m_res.status_code == 200: 
                    cur_mast = m_res.json().get('championPoints', 0)
                    
                tot_mast = cur_mast
                
                if player_entry:
                    cursor.execute("SELECT SUM(am.mastery_points) as db_mast FROM account_mastery am JOIN accounts a ON am.puuid = a.puuid WHERE a.player_id = %s AND a.puuid != %s AND am.champion_id = %s", (player_entry['player_id'], puuid, champ_id))
                    db_res = cursor.fetchone()
                    if db_res and db_res['db_mast']: tot_mast += db_res['db_mast']
                
                tag_disp = tag_disp or (searcher_tag if puuid == target_puuid else p_streak)
                if p_streak == "Winners Queue" and tot_mast > 200000: tag_disp = "YOU'RE COOKED"
                if cur_mast < 50000 and tot_mast > 500000: tag_disp = "SECRET WEAPON"

                db_special_tag = player_entry.get('special_tag') if player_entry else None
                if db_special_tag: tag_disp = db_special_tag

                if p['teamId'] == searcher_team_id:
                    ally_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: ally_streaks += 1
                else:
                    enemy_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: enemy_streaks += 1

            p_payload = {
                "puuid": puuid, "riotId": riot_id,
                "is_streamer": is_streamer, "championId": champ_id, 
                "is_pro": is_pro, "is_creator": is_creator,
                "known_name": player_entry.get('known_name') or player_entry.get('name') if player_entry else None,
                "team": player_entry.get('team') if player_entry else None,
                "role": player_entry.get('role') if player_entry else None,
                "nationality": player_entry.get('nationality') if player_entry else None,
                "mantra": player_entry.get('mantra') if player_entry else None,
                "socials": socials_dict, "smurfs": smurfs_list,
                "rank": rank_data["tier"], "lp": rank_data["lp"],
                "current_mastery": cur_mast, "total_mastery": tot_mast, 
                "tag": tag_disp, "side": "ally" if p['teamId'] == searcher_team_id else "enemy"
            }
            
            if p['teamId'] == searcher_team_id: allies.append(p_payload)
            else: enemies.append(p_payload)

        return {"status": "live", "allies": allies, "enemies": enemies, "ff_angle": (enemy_m_total >= (ally_m_total * 2) and enemy_streaks >= (ally_streaks * 2) and enemy_streaks > 0)}
    except HTTPException:
        raise # Let clean 404s and 429s pass through to the frontend!
    except Exception as e: 
        print(f"CRITICAL ERROR: {e}") 
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        if conn: conn.close()

@app.get("/api/history/{puuid}")
def get_match_history(puuid: str, start: int = 0, count: int = 5):
    try:
        url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
        res = requests.get(url, headers=HEADERS, timeout=5)
        
        if res.status_code == 429: raise HTTPException(status_code=429, detail="Rate limit reached. Please wait 2 minutes.")
        if res.status_code != 200: raise HTTPException(status_code=res.status_code, detail="Riot API Error")
        
        match_ids = res.json()
        history_data = []

        for match_id in match_ids:
            time.sleep(0.4) # Paced buffer to avoid bursting 100/2min
            detail_res = requests.get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}", headers=HEADERS)
            
            if detail_res.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate limit reached while loading games.")
            
            if detail_res.status_code == 200:
                data = detail_res.json()
                me = next((p for p in data['info']['participants'] if p['puuid'] == puuid), None)
                if not me: continue
                
                opponent = next((p for p in data['info']['participants'] if p['teamId'] != me['teamId'] and p['teamPosition'] == me['teamPosition']), None)
                
                perks = me.get('perks', {})
                styles = perks.get('styles', [])
                primary = next((s for s in styles if s['description'] == 'primaryStyle'), {})
                sub = next((s for s in styles if s['description'] == 'subStyle'), {})

                team_kills = sum(p['kills'] for p in data['info']['participants'] if p['teamId'] == me['teamId'])
                kp = int(round((me['kills'] + me['assists']) / max(1, team_kills) * 100))

                history_data.append({
                    "matchId": match_id, "puuid": puuid,
                    "result": "VICTORY" if me['win'] else "DEFEAT", "isWin": me['win'],
                    "myChamp": me['championName'], "oppChamp": opponent['championName'] if opponent else "Unknown",
                    "kda": f"{me['kills']} / {me['deaths']} / {me['assists']}", "kp": f"{kp}%",
                    "time": "Just now" if (int((time.time() - data['info']['gameCreation'] / 1000) / 3600)) < 1 else f"{int((time.time() - data['info']['gameCreation'] / 1000) / 3600)}h ago",
                    "items": [me.get(f'item{i}', 0) for i in range(7)],
                    "runes": {
                        "primaryId": primary.get('style'),
                        "primaryPerks": [p['perk'] for p in primary.get('selections', [])],
                        "subId": sub.get('style'),
                        "subPerks": [p['perk'] for p in sub.get('selections', [])],
                        "statPerks": [perks.get('statPerks', {}).get(k) for k in ['offense', 'flex', 'defense']]
                    }
                })
        return history_data
    except HTTPException:
        raise
    except Exception as e: 
        print(f"History Error: {e}"); 
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@app.get("/api/timeline/{match_id}/{puuid}")
def get_match_timeline(match_id: str, puuid: str):
    try:
        res = requests.get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline", headers=HEADERS)
        if res.status_code == 429: raise HTTPException(status_code=429, detail="Rate limit reached.")
        
        data = res.json()
        p_id = next((p['participantId'] for p in data['info']['participants'] if p['puuid'] == puuid), None)
        
        purchases, skills = [], []
        for frame in data['info']['frames']:
            for event in frame.get('events', []):
                if event.get('participantId') == p_id:
                    if event.get('type') == 'ITEM_PURCHASED':
                        purchases.append({"itemId": event['itemId'], "timestamp": event['timestamp']})
                    elif event.get('type') == 'SKILL_LEVEL_UP':
                        skills.append(event['skillSlot'])
        return {"purchases": purchases, "skills": skills}
    except Exception: return {"purchases": [], "skills": []}