import os
import requests
import time
import urllib.parse
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("RIOT_API_KEY")
RIOT_HEADERS = {"X-Riot-Token": API_KEY}

def ask(prompt, required=False):
    """Prompt helper — returns None on empty unless required."""
    while True:
        val = input(prompt).strip()
        if val:
            return val
        if not required:
            return None
        print("  [!] This field is required.")

def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
    except Exception as e:
        print(f"[!] Could not connect to database: {e}")
        sys.exit(1)

def add_custom_pro():
    print("=== Manual Pro Entry Tool ===\n")

    # ── Identity ──────────────────────────────────────────────────────────────
    known_name  = ask("Known/Display name (required): ", required=True)
    real_name   = ask("Real name (or Enter to skip): ")
    birthday    = ask("Birthday YYYY-MM-DD (or Enter to skip): ")
    nationality = ask("Nationality (or Enter to skip): ")
    role        = ask("Role — Top / Jungle / Mid / Bot / Support (or Enter to skip): ")
    mantra      = ask("Mantra / quote (or Enter to skip): ")

    # ── Special tag ───────────────────────────────────────────────────────────
    print("\nSpecial tags: THE DEV, VIP — leave blank for none.")
    special_tag = ask("Special tag (or Enter to skip): ")

    # ── Team ──────────────────────────────────────────────────────────────────
    team          = ask("\nTeam name (or Enter to skip): ")
    team_logo_url = ask("Team logo URL/path (or Enter to skip): ") if team else None

    # ── Socials ───────────────────────────────────────────────────────────────
    print("\nSocials — paste full URL or just the handle, Enter to skip each.")
    twitch_url    = ask("Twitch: ")
    youtube_url   = ask("YouTube: ")
    twitter_url   = ask("Twitter/X: ")
    leaguepedia   = ask("Leaguepedia URL: ")

    # ── Profile image ─────────────────────────────────────────────────────────
    print("\nProfile image path as served by the backend, e.g. /images/players/you.png")
    print("Leave blank if you haven't added the image file yet.")
    profile_image_url = ask("Profile image path: ")

    # ── Accounts ──────────────────────────────────────────────────────────────
    print("\nEnter Riot IDs one by one (Name#Tag). Empty line when done.")
    accounts_to_add = []
    while True:
        riot_id = input("> Riot ID: ").strip()
        if not riot_id:
            break
        if '#' not in riot_id:
            print("  [!] Must include '#' — e.g. Agurin#EUW")
            continue
        accounts_to_add.append(riot_id)

    if not accounts_to_add:
        print("\nNo accounts entered. Exiting.")
        return

    # is_creator is driven by YouTube presence, not special_tag
    is_creator = bool(youtube_url)

    # ── Commit ────────────────────────────────────────────────────────────────
    print(f"\n--- Saving '{known_name}' with {len(accounts_to_add)} account(s) ---")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        slug_name = known_name.lower().replace(" ", "-")

        cursor.execute("""
            INSERT INTO players (
                name, known_name, real_name, birthday,
                nationality, role, mantra, special_tag,
                team, team_logo_url,
                twitch_url, youtube_url, twitter_url, leaguepedia_url,
                profile_image_url,
                is_pro, is_creator
            )
            VALUES (
                LOWER(%s), %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s
            )
            ON CONFLICT (name) DO UPDATE SET
                known_name        = EXCLUDED.known_name,
                real_name         = COALESCE(EXCLUDED.real_name,         players.real_name),
                birthday          = COALESCE(EXCLUDED.birthday,          players.birthday),
                nationality       = COALESCE(EXCLUDED.nationality,       players.nationality),
                role              = COALESCE(EXCLUDED.role,              players.role),
                mantra            = COALESCE(EXCLUDED.mantra,            players.mantra),
                special_tag       = COALESCE(EXCLUDED.special_tag,       players.special_tag),
                team              = COALESCE(EXCLUDED.team,              players.team),
                team_logo_url     = COALESCE(EXCLUDED.team_logo_url,     players.team_logo_url),
                twitch_url        = COALESCE(EXCLUDED.twitch_url,        players.twitch_url),
                youtube_url       = COALESCE(EXCLUDED.youtube_url,       players.youtube_url),
                twitter_url       = COALESCE(EXCLUDED.twitter_url,       players.twitter_url),
                leaguepedia_url   = COALESCE(EXCLUDED.leaguepedia_url,   players.leaguepedia_url),
                profile_image_url = COALESCE(EXCLUDED.profile_image_url, players.profile_image_url),
                is_pro            = EXCLUDED.is_pro,
                is_creator        = EXCLUDED.is_creator
            RETURNING player_id;
        """, (
            slug_name, known_name, real_name, birthday,
            nationality, role, mantra, special_tag,
            team, team_logo_url,
            twitch_url, youtube_url, twitter_url, leaguepedia,
            profile_image_url,
            bool(team), is_creator
        ))

        player_id = cursor.fetchone()[0]
        print(f"[✓] Player record saved — {known_name} (ID: {player_id})")

        for riot_id in accounts_to_add:
            game_name, tag_line = riot_id.split('#', 1)
            safe_name = urllib.parse.quote(game_name.strip())
            safe_tag  = urllib.parse.quote(tag_line.strip())

            url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
            time.sleep(1.2)
            res = requests.get(url, headers=RIOT_HEADERS)

            if res.status_code == 200:
                puuid = res.json()['puuid']
                cursor.execute("""
                    INSERT INTO accounts (puuid, player_id, riot_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (puuid) DO UPDATE SET
                        riot_id   = EXCLUDED.riot_id,
                        player_id = EXCLUDED.player_id;
                """, (puuid, player_id, riot_id))
                print(f"   -> [OK]     {riot_id}")
            else:
                print(f"   -> [FAILED] {riot_id}  (HTTP {res.status_code})")

        conn.commit()
        print("\n=== Done ===")

    except Exception as e:
        print(f"\n[!] Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_custom_pro()