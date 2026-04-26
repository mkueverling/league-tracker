from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests, os, urllib.parse, psycopg2, time, itertools, re
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)
API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
REGION, PLATFORM = "europe", "euw1"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/images", StaticFiles(directory="../images"), name="images")

# --- TWITCH LIVE-CHECK LOGIC ---
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
twitch_access_token = None
twitch_token_expiry = 0

def get_twitch_token():
    global twitch_access_token, twitch_token_expiry
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET: return None
    if time.time() >= twitch_token_expiry:
        try:
            res = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={TWITCH_CLIENT_ID}&client_secret={TWITCH_CLIENT_SECRET}&grant_type=client_credentials", timeout=5)
            if res.status_code == 200:
                data = res.json()
                twitch_access_token = data['access_token']
                twitch_token_expiry = time.time() + data['expires_in'] - 60
        except Exception as e:
            print(f"Twitch Token Error: {e}")
    return twitch_access_token

def extract_twitch_username(url):
    if not url: return None
    match = re.search(r'twitch\.tv/([^/?]+)', url.lower())
    return match.group(1) if match else None

def check_twitch_live(usernames):
    if not usernames: return set()
    token = get_twitch_token()
    if not token: return set()
    headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
    query = "&".join([f"user_login={u}" for u in usernames[:100]])
    try:
        res = requests.get(f"https://api.twitch.tv/helix/streams?{query}", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return {stream['user_login'].lower() for stream in data.get('data', [])}
    except Exception as e:
        print(f"Twitch API Error: {e}")
    return set()

# --- CHAMPION & ROLE LOGIC ENGINE ---
CHAMP_ID_TO_NAME = {}
try:
    ver_res = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5)
    dd_patch = ver_res.json()[0]
    champ_res = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{dd_patch}/data/en_US/champion.json", timeout=5)
    CHAMP_ID_TO_NAME = {int(v['key']): k for k, v in champ_res.json()['data'].items()}
except Exception as e:
    print(f"Warning: Could not load DDragon Champ Data: {e}")

TOP_CHAMPS = {"Aatrox", "Camille", "ChoGath", "Darius", "DrMundo", "Fiora", "Gangplank", "Garen", "Gnar", "Gwen", "Illaoi", "Irelia", "Jax", "Jayce", "KSante", "Kayle", "Kennen", "Kled", "Malphite", "Mordekaiser", "Nasus", "Olaf", "Ornn", "Pantheon", "Poppy", "Quinn", "Renekton", "Riven", "Rumble", "Sett", "Shen", "Singed", "Sion", "TahmKench", "Teemo", "Tryndamere", "Urgot", "Volibear", "Wukong", "Yorick", "Ambessa"}
JUNGLE_CHAMPS = {"Amumu", "Belveth", "Briar", "Diana", "Ekko", "Elise", "Evelynn", "Fiddlesticks", "Gragas", "Graves", "Hecarim", "Ivern", "JarvanIV", "Karthus", "Kayn", "KhaZix", "Kindred", "LeeSin", "Lillia", "MasterYi", "Nidalee", "Nocturne", "Nunu", "Rammus", "Rengar", "Sejuani", "Shaco", "Shyvana", "Skarner", "Talon", "Udyr", "Vi", "Viego", "Warwick", "XinZhao", "Zac"}
MID_CHAMPS = {"Ahri", "Akali", "Akshan", "Anivia", "Annie", "AurelionSol", "Azir", "Cassiopeia", "Corki", "Ekko", "Fizz", "Galio", "Hwei", "Irelia", "Kassadin", "Katarina", "LeBlanc", "Lissandra", "Malzahar", "Naafiri", "Neeko", "Orianna", "Qiyana", "Ryze", "Sylas", "Syndra", "Talon", "TwistedFate", "Veigar", "Vex", "Viktor", "Vladimir", "Xerath", "Yasuo", "Yone", "Zed", "Zoe", "Mel"}
BOT_CHAMPS = {"Aphelios", "Ashe", "Caitlyn", "Draven", "Ezreal", "Jhin", "Jinx", "Kaisa", "Kalista", "KogMaw", "Lucian", "MissFortune", "Nilah", "Samira", "Sivir", "Smolder", "Tristana", "Twitch", "Varus", "Vayne", "Xayah", "Zeri"}
SUPP_CHAMPS = {"Alistar", "Bard", "Blitzcrank", "Braum", "Janna", "Karma", "Leona", "Lulu", "Milio", "Morgana", "Nami", "Nautilus", "Pyke", "Rakan", "Rell", "Renata", "Senna", "Seraphine", "Sona", "Soraka", "Taric", "Thresh", "Yuumi", "Zilean", "Zyra", "Mel"}

SMITE, TELEPORT, IGNITE, EXHAUST, HEAL, BARRIER, CLEANSE, GHOST = 11, 12, 14, 3, 7, 21, 1, 6

def assign_roles_and_sort(team):
    unassigned = list(team)
    locked_roles = {}
    for p in unassigned[:]:
        if p.get('role'):
            pr = p['role'].lower().strip()
            if pr == "adc": pr = "bot"
            if pr == "jungler": pr = "jungle"
            if pr not in locked_roles:
                locked_roles[pr] = p
                unassigned.remove(p)

    ROLES = ["top", "jungle", "mid", "bot", "support"]
    available_roles = [r for r in ROLES if r not in locked_roles]

    def get_score(p, role):
        score = 0
        cname = CHAMP_ID_TO_NAME.get(p.get('championId'), "")
        has_smite = p.get('spell1Id') == SMITE or p.get('spell2Id') == SMITE
        has_tp = p.get('spell1Id') == TELEPORT or p.get('spell2Id') == TELEPORT
        has_heal = p.get('spell1Id') == HEAL or p.get('spell2Id') == HEAL
        has_exhaust = p.get('spell1Id') == EXHAUST or p.get('spell2Id') == EXHAUST
        has_ignite = p.get('spell1Id') == IGNITE or p.get('spell2Id') == IGNITE

        if role == "top" and cname in TOP_CHAMPS: score += 500
        if role == "jungle" and cname in JUNGLE_CHAMPS: score += 500
        if role == "mid" and cname in MID_CHAMPS: score += 500
        if role == "bot" and cname in BOT_CHAMPS: score += 500
        if role == "support" and cname in SUPP_CHAMPS: score += 500

        if role == "jungle":
            if has_smite: score += 2000
            else: score -= 2000
        else:
            if has_smite: score -= 2000

        if role == "top" and has_tp: score += 20
        if role == "mid" and (has_tp or has_ignite): score += 10
        if role == "bot" and has_heal: score += 20
        if role == "support" and (has_exhaust or has_ignite): score += 20
        if role == "support" and has_tp: score -= 100

        return score

    best_score = -float('inf')
    best_assignment = {}
    for perm in itertools.permutations(available_roles):
        current_score = sum(get_score(p, perm[i]) for i, p in enumerate(unassigned))
        if current_score > best_score:
            best_score = current_score
            best_assignment = {perm[i]: p for i, p in enumerate(unassigned)}

    final_roles = {**locked_roles, **best_assignment}
    ordered = []
    for r in ROLES:
        if r in final_roles:
            final_roles[r]['guessed_role'] = r
            ordered.append(final_roles[r])
            
    for p in unassigned:
        if p not in ordered:
            p['guessed_role'] = "fill"
            ordered.append(p)
            
    return ordered

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), 
        user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"), connect_timeout=5
    )

def get_rank_info(puuid):
    if not puuid: return {"tier": "unranked", "division": "", "lp": 0}
    try:
        url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        res = requests.get(url, headers=HEADERS, timeout=3)
        if res.status_code == 200:
            for entry in res.json():
                if entry.get('queueType') == 'RANKED_SOLO_5x5':
                    return {"tier": entry.get('tier', 'unranked').lower(), "division": entry.get('rank', ''), "lp": entry.get('leaguePoints', 0)}
    except Exception: pass
    return {"tier": "unranked", "division": "", "lp": 0}

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
        
        if acc_res.status_code == 429: raise HTTPException(status_code=429, detail="Riot API rate limit reached. Please wait 2 minutes.")
        if acc_res.status_code != 200: raise HTTPException(status_code=404, detail="Player not found")
        
        target_puuid = acc_res.json().get('puuid')

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("""
                INSERT INTO tracked_users (puuid, last_searched) 
                VALUES (%s, NOW()) 
                ON CONFLICT (puuid) DO UPDATE SET last_searched = NOW();
            """, (target_puuid,))
            conn.commit()
        except Exception as db_err:
            print(f"[!] Tracking Table Error: {db_err}")

        spec_url = f"https://{PLATFORM}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{target_puuid}"
        spec_res = requests.get(spec_url, headers=HEADERS, timeout=5)
        
        if spec_res.status_code == 429: raise HTTPException(status_code=429, detail="Riot API rate limit reached.")
        if spec_res.status_code != 200: return {"status": "history"}

        game_data = spec_res.json()

        searcher_team_id = 100
        search_string = f"{name}#{tag}".lower()
        lobby_puuids = []
        
        for p in game_data['participants']:
            p_puuid = p.get('puuid')
            p_riot_id = p.get('riotId', '').lower()
            if p_puuid: lobby_puuids.append(p_puuid)
            if (p_puuid and p_puuid == target_puuid) or (p_riot_id == search_string):
                searcher_team_id = p['teamId']

        searcher_tag = get_streak_tag(cursor, target_puuid)
        
        familiar_data = {}
        other_puuids = [pid for pid in lobby_puuids if pid != target_puuid]
        if target_puuid and other_puuids:
            try:
                cursor.execute("""
                    WITH target_puuids AS (
                        SELECT puuid FROM accounts 
                        WHERE player_id = (SELECT player_id FROM accounts WHERE puuid = %(target)s)
                        UNION SELECT %(target)s
                    ),
                    lobby_accounts AS (
                        SELECT l.puuid AS lobby_puuid, COALESCE(a2.puuid, l.puuid) AS alias_puuid
                        FROM unnest(%(lobby)s::varchar[]) l(puuid)
                        LEFT JOIN accounts a1 ON a1.puuid = l.puuid
                        LEFT JOIN accounts a2 ON a2.player_id = a1.player_id
                    )
                    SELECT 
                        la.lobby_puuid as puuid,
                        SUM(CASE WHEN mp_target.win = true AND mp_target.team_id = mp_other.team_id THEN 1 ELSE 0 END) as wins_with,
                        SUM(CASE WHEN mp_target.win = false AND mp_target.team_id = mp_other.team_id THEN 1 ELSE 0 END) as losses_with,
                        SUM(CASE WHEN mp_target.win = true AND mp_target.team_id != mp_other.team_id THEN 1 ELSE 0 END) as wins_against,
                        SUM(CASE WHEN mp_target.win = false AND mp_target.team_id != mp_other.team_id THEN 1 ELSE 0 END) as losses_against
                    FROM match_participants mp_target
                    JOIN match_participants mp_other ON mp_target.match_id = mp_other.match_id
                    JOIN target_puuids tp ON mp_target.puuid = tp.puuid
                    JOIN lobby_accounts la ON mp_other.puuid = la.alias_puuid
                    WHERE la.lobby_puuid != %(target)s
                      AND mp_other.puuid NOT IN (SELECT puuid FROM target_puuids)
                    GROUP BY la.lobby_puuid;
                """, {"target": target_puuid, "lobby": other_puuids})
                
                for row in cursor.fetchall():
                    familiar_data[row['puuid']] = dict(row)
            except Exception as e:
                pass 

        allies, enemies = [], []
        ally_m_total, enemy_m_total, ally_streaks, enemy_streaks = 0, 0, 0, 0
        base_url = "http://localhost:8000"
        
        twitch_check_map = {} 

        for p in game_data['participants']:
            puuid = p.get('puuid').strip() if p.get('puuid') else None
            riot_id = p.get('riotId', 'Unknown').strip()
            champ_id = p.get('championId', 0)
            
            is_streamer = puuid is None
            player_entry, cur_mast, tot_mast, tag_disp = None, 0, 0, None
            rank_data = {"tier": "unranked", "division": "", "lp": 0}
            smurfs_list = []
            ladder_rank = None

            is_pro = False
            is_creator = False
            db_special_tag = None
            socials_dict = {}
            real_img = None
            team_logo = None
            leaguepedia = None
            real_name = None
            birthday = None

            perks = p.get('perks', {})
            perk_ids = perks.get('perkIds', [])
            primary_perk = perk_ids[0] if len(perk_ids) > 0 else 0
            sub_style = perks.get('perkSubStyle', 0)

            if not is_streamer:
                participant_slug = riot_id.split('#')[0].strip().replace(" ", "-")
                cursor.execute("""
                    SELECT p.* FROM players p 
                    JOIN accounts a ON p.player_id = a.player_id 
                    WHERE a.puuid = %s 
                       OR LOWER(a.riot_id) = LOWER(%s) 
                       OR p.name = LOWER(%s)
                    LIMIT 1
                """, (puuid, riot_id, participant_slug))
                player_entry = cursor.fetchone()
                
                rank_data = get_rank_info(puuid)
                p_streak = get_streak_tag(cursor, puuid)

                try:
                    cursor.execute("SELECT rank FROM apex_ladder WHERE puuid = %s", (puuid,))
                    lr_row = cursor.fetchone()
                    ladder_rank = lr_row['rank'] if lr_row else None
                except Exception:
                    pass

                if player_entry:
                    cursor.execute("SELECT riot_id FROM accounts WHERE player_id = %s AND riot_id != %s", (player_entry['player_id'], riot_id))
                    smurfs_list = [row['riot_id'] for row in cursor.fetchall() if row['riot_id']]

                    t_twitch = player_entry.get('twitch_url') or player_entry.get('twitch')
                    t_twitter = player_entry.get('twitter_url') or player_entry.get('twitter')
                    t_youtube = player_entry.get('youtube_url') or player_entry.get('youtube')

                    if t_twitch and str(t_twitch).strip() and str(t_twitch).strip().lower() != "none": socials_dict["Twitch"] = str(t_twitch).strip()
                    if t_twitter and str(t_twitter).strip() and str(t_twitter).strip().lower() != "none": socials_dict["Twitter"] = str(t_twitter).strip()
                    if t_youtube and str(t_youtube).strip() and str(t_youtube).strip().lower() != "none": socials_dict["YouTube"] = str(t_youtube).strip()

                    is_pro = bool(player_entry.get('team')) if player_entry else False
                    is_creator = "YouTube" in socials_dict

                    raw_img = player_entry.get('profile_image_url')
                    if raw_img and str(raw_img).strip().lower() != "none":
                        raw_img = raw_img.replace('\\', '/').strip()
                        if not raw_img.startswith('/'):
                            raw_img = '/' + raw_img
                        real_img = base_url + raw_img
                        
                    raw_logo = player_entry.get('team_logo_url')
                    if raw_logo and str(raw_logo).strip().lower() != "none":
                        raw_logo = raw_logo.replace('\\', '/').strip()
                        if not raw_logo.startswith('/'):
                            raw_logo = '/' + raw_logo
                        team_logo = base_url + raw_logo
                        
                    lp_url = player_entry.get('leaguepedia_url')
                    if lp_url and str(lp_url).strip().lower() != "none":
                        leaguepedia = lp_url
                        
                    real_name = player_entry.get('real_name')
                    birthday = str(player_entry.get('birthday')) if player_entry.get('birthday') else None

                time.sleep(0.1) 
                m_res = requests.get(f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champ_id}", headers=HEADERS, timeout=3)
                
                if m_res.status_code == 429: cur_mast = 0 
                elif m_res.status_code == 200: cur_mast = m_res.json().get('championPoints', 0)
                    
                tot_mast = cur_mast
                
                if player_entry:
                    cursor.execute("SELECT SUM(am.mastery_points) as db_mast FROM account_mastery am JOIN accounts a ON am.puuid = a.puuid WHERE a.player_id = %s AND a.puuid != %s AND am.champion_id = %s", (player_entry['player_id'], puuid, champ_id))
                    db_res = cursor.fetchone()
                    if db_res and db_res['db_mast']: tot_mast += int(db_res['db_mast'])
                
                tag_disp = tag_disp or (searcher_tag if puuid == target_puuid else p_streak)
                if p_streak == "Winners Queue" and tot_mast > 200000: tag_disp = "YOU'RE COOKED"
                if tot_mast >= 300000 and cur_mast <= (tot_mast * 0.3): tag_disp = "SECRET WEAPON"
                
                if tot_mast >= 1_500_000: tag_disp = "THREAT"
                if tot_mast >= 3_000_000: tag_disp = "OBSESSED"
                if tot_mast >= 5_000_000: tag_disp = "CREATURE"

                db_special_tag = player_entry.get('special_tag') if player_entry else None
                if db_special_tag: tag_disp = db_special_tag

                if p['teamId'] == searcher_team_id:
                    ally_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: ally_streaks += 1
                else:
                    enemy_m_total += tot_mast
                    if tag_disp in ["Winning", "On Fire", "Winners Queue"]: enemy_streaks += 1
                    
                if "Twitch" in socials_dict:
                    t_user = extract_twitch_username(socials_dict["Twitch"])
                    if t_user:
                        twitch_check_map[t_user] = puuid

            p_payload = {
                "puuid": puuid, "riotId": riot_id,
                "is_streamer": is_streamer, "championId": champ_id, 
                "spell1Id": p.get('spell1Id'), "spell2Id": p.get('spell2Id'), 
                "primary_perk": primary_perk, "sub_style": sub_style,
                "is_pro": is_pro, "is_creator": is_creator,
                "is_vip": (db_special_tag == 'VIP'),
                "is_live": False,
                "known_name": player_entry.get('known_name') or player_entry.get('name') if player_entry else None,
                "ladder_rank": ladder_rank, 
                "team": player_entry.get('team') if player_entry else None,
                "role": player_entry.get('role') if player_entry else None,
                "nationality": player_entry.get('nationality') if player_entry else None,
                "mantra": player_entry.get('mantra') if player_entry else None,
                "real_name": real_name, "birthday": birthday,
                "real_img": real_img, "team_logo": team_logo, "leaguepedia": leaguepedia,
                "socials": socials_dict, "smurfs": smurfs_list,
                "rank": rank_data["tier"], "division": rank_data.get("division", ""), "lp": rank_data["lp"],
                "current_mastery": cur_mast, "total_mastery": tot_mast, 
                "tag": tag_disp, "side": "ally" if p['teamId'] == searcher_team_id else "enemy",
                "familiar_stats": familiar_data.get(puuid) 
            }
            
            if p['teamId'] == searcher_team_id: allies.append(p_payload)
            else: enemies.append(p_payload)

        if twitch_check_map:
            live_users = check_twitch_live(list(twitch_check_map.keys()))
            live_puuids = {twitch_check_map[u] for u in live_users if u in twitch_check_map}
            for p in allies + enemies:
                if p["puuid"] in live_puuids:
                    p["is_live"] = True

        def has_pro_synergy(team_list):
            teams_count = {}
            for participant in team_list:
                t = participant.get("team")
                if t:
                    teams_count[t] = teams_count.get(t, 0) + 1
            return any(count >= 2 for count in teams_count.values())

        return {
            "status": "live",
            "game_length": game_data.get('gameLength', 0),
            "queue_id": game_data.get('gameQueueConfigId', 0),
            "allies": assign_roles_and_sort(allies), 
            "enemies": assign_roles_and_sort(enemies), 
            "ff_angle": (enemy_m_total >= (ally_m_total * 2) and enemy_streaks >= (ally_streaks * 2) and enemy_streaks > 0),
            "ally_synergy": has_pro_synergy(allies),
            "enemy_synergy": has_pro_synergy(enemies)
        }
    except HTTPException: raise 
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
            time.sleep(0.4) 
            detail_res = requests.get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}", headers=HEADERS)
            
            if detail_res.status_code == 429: raise HTTPException(status_code=429, detail="Rate limit reached while loading games.")
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
                    "duration": data['info']['gameDuration'],
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
    except HTTPException: raise
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

@app.get("/api/team/{team_name}")
def get_team_roster(team_name: str):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT known_name, name, role, profile_image_url, nationality
            FROM players 
            WHERE team = %s
            ORDER BY 
                CASE role 
                    WHEN 'Top' THEN 1 
                    WHEN 'Jungle' THEN 2 
                    WHEN 'Mid' THEN 3 
                    WHEN 'Bot' THEN 4 
                    WHEN 'ADC' THEN 4
                    WHEN 'Support' THEN 5 
                    ELSE 6 
                END
        """, (team_name,))
        
        roster = cursor.fetchall()
        base_url = "http://localhost:8000"
        formatted_roster = []
        
        for p in roster:
            raw_img = p.get('profile_image_url')
            real_img = base_url + raw_img if raw_img and str(raw_img).strip().lower() != "none" and raw_img.startswith('/') else raw_img
            
            formatted_roster.append({
                "name": p.get('known_name') or p.get('name'),
                "role": p.get('role'),
                "image": real_img,
                "nationality": p.get('nationality')
            })
            
        return {"team": team_name, "roster": formatted_roster}
    except Exception as e:
        print(f"Roster Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team roster")
    finally:
        if conn: conn.close()

@app.get("/api/patch/{champion_key}")
def get_patch_notes(champion_key: str):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT DISTINCT patch_version
            FROM patch_notes
            WHERE LOWER(champion_key) = LOWER(%s)
            ORDER BY patch_version DESC
            LIMIT 1
        """, (champion_key,))
        row = cursor.fetchone()
        if not row:
            return {"champion_key": champion_key, "patch_version": None, "change_type": None, "abilities": []}

        patch_version = row["patch_version"]

        cursor.execute("""
            SELECT ability_slot, ability_name, change_type, notes
            FROM patch_notes
            WHERE LOWER(champion_key) = LOWER(%s) AND patch_version = %s
            ORDER BY
                CASE ability_slot
                    WHEN 'base'    THEN 0
                    WHEN 'passive' THEN 1
                    WHEN 'q'       THEN 2
                    WHEN 'w'       THEN 3
                    WHEN 'e'       THEN 4
                    WHEN 'r'       THEN 5
                    ELSE 6
                END
        """, (champion_key, patch_version))

        abilities = cursor.fetchall()
        if not abilities:
            return {"champion_key": champion_key, "patch_version": patch_version, "change_type": None, "abilities": []}

        all_types = [a["change_type"] for a in abilities]
        overall = "nerf" if "nerf" in all_types else ("buff" if "buff" in all_types else "change")

        return {
            "champion_key":  champion_key,
            "patch_version": patch_version,
            "change_type":   overall,
            "abilities": [
                {
                    "slot":  a["ability_slot"],
                    "name":  a["ability_name"],
                    "notes": a["notes"]
                }
                for a in abilities
            ]
        }
    except Exception as e:
        print(f"Patch notes error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch patch notes")
    finally:
        if conn: conn.close()

@app.get("/api/search")
def search_players(q: str = ""):
    if len(q) < 2: return []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        search_term = f"%{q.lower()}%"
        
        cursor.execute("""
            SELECT a.riot_id, p.known_name, p.name, p.profile_image_url
            FROM accounts a
            LEFT JOIN players p ON a.player_id = p.player_id
            WHERE LOWER(a.riot_id) LIKE %s 
               OR LOWER(p.known_name) LIKE %s 
               OR LOWER(p.name) LIKE %s
            LIMIT 5
        """, (search_term, search_term, search_term))
        
        results = cursor.fetchall()
        base_url = "http://localhost:8000"
        formatted = []
        for r in results:
            img = r.get('profile_image_url')
            if img and str(img).strip().lower() != "none":
                img = img.replace('\\', '/').strip()
                if not img.startswith('/'): img = '/' + img
                img = base_url + img
            else:
                img = ""
                
            formatted.append({
                "riot_id": r['riot_id'],
                "name": r['known_name'] or r['name'] or "",
                "image": img
            })
        return formatted
    except Exception as e:
        print(f"Search Error: {e}")
        return []
    finally:
        if conn: conn.close()