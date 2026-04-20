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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- RATE LIMIT TUNING ---
BASE_DELAY_CARGO       = 1.5   # between small cargo/api calls
BASE_DELAY_IMAGE_QUERY = 3.0   # between (batched) PlayerImages queries
BASE_DELAY_DOWNLOAD    = 2.0   # between actual file downloads
INITIAL_BACKOFF        = 60    # first backoff after a rate-limit (seconds)
MAX_BACKOFF            = 900   # cap at 15 minutes
MAX_RETRIES            = 6
CARGO_BATCH_SIZE       = 500   # Players fetched per outer loop
IMAGE_QUERY_BATCH      = 40    # Players per batched PlayerImages query
BATCH_BREATHER         = 60    # sleep between outer batches


# --- DB ---
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# --- RATE-LIMIT-SAFE API WRAPPER ---
def safe_api_call(func, *args, description="API call", **kwargs):
    """
    Run a Fandom/Cargo call with exponential backoff on rate limits.
    Returns None if all retries are exhausted.
    """
    delay = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            is_rate_limit = any(k in msg for k in (
                "ratelimit", "rate limit", "ratelimited",
                "throttle", "too many requests", "429"
            ))
            if attempt >= MAX_RETRIES:
                print(f"      [!] Giving up on {description} after {attempt} attempts: {e}")
                return None
            if is_rate_limit:
                print(f"      [!] Rate limited on {description} "
                      f"(attempt {attempt}/{MAX_RETRIES}). Sleeping {delay}s...")
            else:
                print(f"      [!] Transient error on {description}: {e}. Sleeping {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF)
    return None


# --- HELPERS ---
def extract_image_priority(filename):
    if not filename:
        return 0
    year_match = re.search(r'(20\d{2})', filename)
    year = int(year_match.group(1)) if year_match else 0
    score = year * 10
    fn_lower = filename.lower()
    if 'split 2' in fn_lower:   score += 4
    elif 'summer' in fn_lower:  score += 3
    elif 'split 1' in fn_lower: score += 2
    elif 'spring' in fn_lower:  score += 1
    return score


def _local_path_if_exists(target_folder, prefix, public_root):
    """Return the public URL path if a file with any common extension already exists."""
    base = prefix.replace(' ', '_').lower()
    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        p = os.path.join(target_folder, f"{base}.{ext}")
        if os.path.exists(p):
            return f"/{public_root}/{base}.{ext}"
    return None


def local_portrait_path(player_id):
    return _local_path_if_exists(PRO_IMAGE_DIR, player_id, "images/pros")


def local_team_logo_path(team_name):
    return _local_path_if_exists(TEAM_IMAGE_DIR, team_name, "images/teams")


def get_fandom_url(site, filename):
    if not filename:
        return None

    def _query():
        time.sleep(BASE_DELAY_CARGO)
        response = site.client.api(
            action="query", format="json",
            titles=f"File:{filename}", prop="imageinfo", iiprop="url"
        )
        pages = response.get("query", {}).get("pages", {})
        for pg in pages.values():
            if "imageinfo" in pg:
                return pg["imageinfo"][0]["url"]
        return None

    return safe_api_call(_query, description=f"image URL for {filename}")


def download_file(site, filename, target_folder, prefix=""):
    """
    Save a remote Fandom file locally. Checks disk FIRST so we never hit the API
    for a file we already have.
    """
    if not filename:
        return None

    ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
    ext = re.sub(r'[^a-z0-9]', '', ext) or 'png'
    local_filename = f"{prefix.replace(' ', '_').lower()}.{ext}"
    filepath = os.path.join(target_folder, local_filename)
    public_rel = f"/{target_folder.split('public/')[1]}/{local_filename}"

    if os.path.exists(filepath):
        return public_rel

    url = get_fandom_url(site, filename)
    if not url:
        return None

    time.sleep(BASE_DELAY_DOWNLOAD)
    for attempt in range(1, 4):
        try:
            res = requests.get(url, stream=True, headers=HEADERS, timeout=20)
            if res.status_code == 429:
                wait = 60 * attempt
                print(f"      [!] HTTP 429 on download ({filename}). Sleeping {wait}s...")
                time.sleep(wait)
                continue
            if res.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                print(f"      [✓] Saved: {local_filename}")
                return public_rel
            print(f"      [!] Download status {res.status_code} for {filename}")
            return None
        except Exception as e:
            print(f"      [!] Download error for {filename} (attempt {attempt}): {e}")
            time.sleep(10 * attempt)
    return None


def batch_fetch_player_images(site, player_ids):
    """
    One Cargo call returns image rows for ~40 players instead of 40 separate calls.
    Returns {player_id: best_filename}.
    """
    if not player_ids:
        return {}

    def _esc(s):
        return s.replace("\\", "\\\\").replace("'", "\\'")

    where_clause = " OR ".join(f"Link = '{_esc(pid)}'" for pid in player_ids)

    def _query():
        time.sleep(BASE_DELAY_IMAGE_QUERY)
        return site.cargo_client.query(
            tables="PlayerImages",
            fields="Link, FileName",
            where=where_clause,
            limit=500
        )

    rows = safe_api_call(
        _query,
        description=f"batched PlayerImages for {len(player_ids)} players"
    )
    if not rows:
        return {}

    grouped = {}
    for r in rows:
        link = r.get("Link")
        fn = r.get("FileName")
        if not link or not fn:
            continue
        grouped.setdefault(link, []).append(fn)

    return {link: max(files, key=extract_image_priority)
            for link, files in grouped.items()}


# --- MAIN SYNC ---
def fetch_and_upsert_fandom_pros():
    print("DEBUG: Syncing Players with Tie-Breaker + Rate-Limit Hardening...")
    credentials = AuthCredentials(
        username=os.getenv("FANDOM_USERNAME"),
        password=os.getenv("FANDOM_PASSWORD")
    )
    site = EsportsClient('lol', credentials=credentials)

    conn = get_db_connection()
    cursor = conn.cursor()

    offset = 0
    team_logo_cache = {}  # per-run cache for shared team logos

    while True:
        print(f"\n--- Fetching Batch Metadata (Offset: {offset}) ---")

        def _cargo_batch():
            return site.cargo_client.query(
                tables="Players",
                fields=("ID, Country, Birthdate, Role, Team, Twitter, Youtube, "
                        "IsPersonality, IsSubstitute, IsTrainee, IsRetired"),
                order_by="ID", limit=CARGO_BATCH_SIZE, offset=offset
            )

        cargo_results = safe_api_call(_cargo_batch, description="Players batch")
        if cargo_results is None:
            print("   [!] Could not fetch batch after retries. Sleeping 5m and retrying...")
            time.sleep(300)
            continue
        if not cargo_results:
            break

        # --- 1) Resolve DB matches for the whole batch up front ---
        resolved = []  # [(db_player_id, cargo_item, needs_image)]
        for item in cargo_results:
            f_id = item.get("ID")
            if not f_id:
                continue
            f_role = item.get("Role")
            f_country = item.get("Country")
            slugified = f_id.lower().replace(" ", "-")

            cursor.execute("""
                SELECT player_id FROM players 
                WHERE (name = %s OR known_name ILIKE %s)
                ORDER BY 
                    (CASE WHEN role ILIKE %s THEN 1 ELSE 0 END) + 
                    (CASE WHEN nationality ILIKE %s THEN 1 ELSE 0 END) DESC
                LIMIT 1
            """, (
                slugified, f_id,
                f"%{f_role}%" if f_role else "IMPOSSIBLE_MATCH",
                f"%{f_country}%" if f_country else "IMPOSSIBLE_MATCH"
            ))
            match = cursor.fetchone()
            if not match:
                continue
            needs_image = local_portrait_path(f_id) is None
            resolved.append((match[0], item, needs_image))

        need_lookup = [it.get("ID") for _, it, n in resolved if n]
        print(f"  -> {len(resolved)} DB matches in batch; "
              f"{len(need_lookup)} need image lookup "
              f"({len(resolved) - len(need_lookup)} cached locally)")

        # --- 2) Batched image-metadata queries ---
        image_map = {}
        for i in range(0, len(need_lookup), IMAGE_QUERY_BATCH):
            chunk = need_lookup[i:i + IMAGE_QUERY_BATCH]
            image_map.update(batch_fetch_player_images(site, chunk))

        # --- 3) Download + upsert each player ---
        for p_id, item, _ in resolved:
            f_id = item.get("ID")
            f_role = item.get("Role")
            f_country = item.get("Country")
            print(f" [+] Processing '{f_id}'")

            # Portrait: prefer local, else download whatever batch query found.
            portrait_local = local_portrait_path(f_id)
            if portrait_local is None:
                best_file = image_map.get(f_id)
                if best_file:
                    portrait_local = download_file(
                        site, best_file, PRO_IMAGE_DIR, f_id
                    )

            # Team logo: use per-run in-memory cache + disk cache.
            team_name = item.get("Team")
            team_logo_local = None
            if team_name:
                if team_name in team_logo_cache:
                    team_logo_local = team_logo_cache[team_name]
                else:
                    team_logo_local = local_team_logo_path(team_name)
                    if team_logo_local is None:
                        team_logo_local = download_file(
                            site, f"{team_name}logo square.png",
                            TEAM_IMAGE_DIR, team_name
                        )
                    team_logo_cache[team_name] = team_logo_local

            def format_social(val, base_url):
                if not val:
                    return None
                return val if val.startswith("http") else f"{base_url}{val.replace('@', '')}"

            f_twitter = format_social(item.get("Twitter"), "https://twitter.com/")
            f_youtube = format_social(item.get("Youtube"), "https://youtube.com/")
            f_leaguepedia = f"https://lol.fandom.com/wiki/{f_id.replace(' ', '_')}"

            try:
                def to_bool(val):
                    return str(val) == '1'

                f_birth = item.get("Birthdate")
                cursor.execute("""
                    UPDATE players SET 
                        known_name        = COALESCE(players.known_name, %s),
                        nationality       = COALESCE(players.nationality, %s),
                        role              = COALESCE(players.role, %s), 
                        team              = %s,
                        birthday          = %s,
                        profile_image_url = %s,
                        team_logo_url     = %s,
                        twitter_url       = COALESCE(players.twitter_url, %s),
                        youtube_url       = COALESCE(players.youtube_url, %s),
                        leaguepedia_url   = %s,
                        is_pro            = TRUE,
                        is_personality    = %s,
                        is_substitute     = %s,
                        is_trainee        = %s,
                        is_retired        = %s
                    WHERE player_id = %s;
                """, (
                    f_id, f_country, f_role, team_name,
                    f_birth if f_birth and len(f_birth) > 5 else None,
                    portrait_local, team_logo_local,
                    f_twitter, f_youtube, f_leaguepedia,
                    to_bool(item.get("IsPersonality")),
                    to_bool(item.get("IsSubstitute")),
                    to_bool(item.get("IsTrainee")),
                    to_bool(item.get("IsRetired")),
                    p_id
                ))
                print("      [✓] DB Updated")
            except Exception as sql_err:
                print(f"      [!] SQL Error: {sql_err}")

            # Small breather — most heavy work is already batched.
            time.sleep(0.5)

        conn.commit()
        offset += CARGO_BATCH_SIZE
        print(f"  -> Batch committed. {BATCH_BREATHER}s breather...")
        time.sleep(BATCH_BREATHER)

    cursor.close()
    conn.close()
    print("\nDONE.")


if __name__ == "__main__":
    fetch_and_upsert_fandom_pros()
