import os
import time
import requests
import psycopg2
import re
from mwrogue.esports_client import EsportsClient
from mwrogue.auth_credentials import AuthCredentials
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

PRO_IMAGE_DIR = "public/images/pros"
TEAM_IMAGE_DIR = "public/images/teams"
os.makedirs(PRO_IMAGE_DIR, exist_ok=True)
os.makedirs(TEAM_IMAGE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def extract_image_priority(filename):
    if not filename: return 0
    year_match = re.search(r'(20\d{2})', filename)
    year = int(year_match.group(1)) if year_match else 0
    score = year * 10
    fn_lower = filename.lower()
    if 'split 2' in fn_lower: score += 4
    elif 'summer' in fn_lower: score += 3
    elif 'split 1' in fn_lower: score += 2
    elif 'spring' in fn_lower: score += 1
    return score

def get_fandom_url(site, filename):
    if not filename: return None
    try:
        time.sleep(1.2) 
        response = site.client.api(action="query", format="json", titles=f"File:{filename}", prop="imageinfo", iiprop="url")
        pages = response.get("query", {}).get("pages", {})
        for pg in pages.values():
            if "imageinfo" in pg: return pg["imageinfo"][0]["url"]
    except Exception: return None
    return None

def download_file(site, filename, target_folder, prefix=""):
    if not filename: return None
    url = get_fandom_url(site, filename)
    if not url: return None

    ext = filename.split('.')[-1] if '.' in filename else 'png'
    local_filename = f"{prefix.replace(' ', '_').lower()}.{ext}"
    filepath = os.path.join(target_folder, local_filename)
    
    if os.path.exists(filepath):
        return f"/{target_folder.split('public/')[1]}/{local_filename}"
        
    time.sleep(2.0) 
    try:
        res = requests.get(url, stream=True, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in res.iter_content(1024): f.write(chunk)
            print(f"      [✓] Saved: {local_filename}")
            return f"/{target_folder.split('public/')[1]}/{local_filename}"
    except Exception: pass
    return None

def fetch_and_upsert_fandom_pros():
    print("DEBUG: Syncing Players with Tie-Breaker Collision Protection...")
    credentials = AuthCredentials(username=os.getenv("FANDOM_USERNAME"), password=os.getenv("FANDOM_PASSWORD"))
    site = EsportsClient('lol', credentials=credentials)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    offset = 0 
    limit = 500
    
    while True:
        print(f"\n--- Fetching Batch Metadata (Offset: {offset}) ---")
        try:
            cargo_results = site.cargo_client.query(
                tables="Players",
                fields="ID, Country, Birthdate, Role, Team, Twitter, Youtube, IsPersonality, IsSubstitute, IsTrainee, IsRetired",
                order_by="ID", limit=limit, offset=offset
            )
        except Exception as e:
            print(f"   [!] Cargo Batch Error. Sleeping 5m..."); time.sleep(300); continue

        if not cargo_results: break

        for item in cargo_results:
            f_id = item.get("ID")
            f_role = item.get("Role")
            f_country = item.get("Country")
            
            if not f_id: continue
            
            slugified = f_id.lower().replace(" ", "-")
            
            # --- TIE-BREAKER LOGIC ---
            # Finds ALL players with the matching name.
            # If a duplicate exists, it scores them (+1 for matching role, +1 for matching country).
            # It sorts by the highest score and picks the top 1.
            cursor.execute("""
                SELECT player_id FROM players 
                WHERE (name = %s OR known_name ILIKE %s)
                ORDER BY 
                    (CASE WHEN role ILIKE %s THEN 1 ELSE 0 END) + 
                    (CASE WHEN nationality ILIKE %s THEN 1 ELSE 0 END) DESC
                LIMIT 1
            """, (
                slugified, 
                f_id, 
                f"%{f_role}%" if f_role else "IMPOSSIBLE_MATCH", 
                f"%{f_country}%" if f_country else "IMPOSSIBLE_MATCH"
            ))
            
            match = cursor.fetchone()

            if match:
                p_id = match[0]
                print(f" [+] Processing '{f_id}'")
                
                # 1. Sequential Image Metadata Query
                portrait_local = None
                try:
                    time.sleep(2.5) 
                    img_query = site.cargo_client.query(
                        tables="PlayerImages",
                        fields="FileName",
                        where=f"Link = '{f_id}'"
                    )
                    if img_query:
                        latest_img_name = max(img_query, key=lambda x: extract_image_priority(x.get("FileName")))
                        portrait_local = download_file(site, latest_img_name, PRO_IMAGE_DIR, f_id)
                except Exception as e:
                    if "ratelimited" in str(e).lower():
                        print("      [!] Rate limited during image query. Sleeping 60s...")
                        time.sleep(60)
                    else:
                        print(f"      [!] Error fetching image metadata: {e}")

                # 2. Team Logo
                team_name = item.get("Team")
                team_logo_local = None
                if team_name:
                    team_logo_local = download_file(site, f"{team_name}logo square.png", TEAM_IMAGE_DIR, team_name)

                # 3. Data Processing
                def format_social(val, base_url):
                    if not val: return None
                    return val if val.startswith("http") else f"{base_url}{val.replace('@', '')}"

                f_twitter = format_social(item.get("Twitter"), "https://twitter.com/")
                f_youtube = format_social(item.get("Youtube"), "https://youtube.com/")
                f_leaguepedia = f"https://lol.fandom.com/wiki/{f_id.replace(' ', '_')}"

                # 4. SQL Update
                try:
                    def to_bool(val): return str(val) == '1'
                    f_birth = item.get("Birthdate")
                    cursor.execute("""
                        UPDATE players SET 
                            known_name = COALESCE(players.known_name, %s),
                            nationality = COALESCE(players.nationality, %s),
                            role = COALESCE(players.role, %s), 
                            team = %s, birthday = %s,
                            profile_image_url = %s, team_logo_url = %s,
                            twitter_url = COALESCE(players.twitter_url, %s),
                            youtube_url = COALESCE(players.youtube_url, %s),
                            leaguepedia_url = %s, is_pro = TRUE,
                            is_personality = %s, is_substitute = %s, is_trainee = %s, is_retired = %s
                        WHERE player_id = %s;
                    """, (f_id, f_country, f_role, team_name, 
                          f_birth if f_birth and len(f_birth) > 5 else None,
                          portrait_local, team_logo_local, f_twitter, f_youtube, f_leaguepedia,
                          to_bool(item.get("IsPersonality")), to_bool(item.get("IsSubstitute")),
                          to_bool(item.get("IsTrainee")), to_bool(item.get("IsRetired")), p_id))
                    print(f"      [✓] DB Updated")
                except Exception as sql_err:
                    print(f"      [!] SQL Error: {sql_err}")
                
                time.sleep(3.0)

        conn.commit()
        offset += limit
        print("  -> Batch committed. 60s breather...")
        time.sleep(60) 
        
    cursor.close(); conn.close()

if __name__ == "__main__":
    fetch_and_upsert_fandom_pros()