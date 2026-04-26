"""
scrape-patch-notes.py
Run manually every two weeks after a new patch drops:
    python scrape-patch-notes.py

SQL migration — run once before first use:
    CREATE TABLE IF NOT EXISTS patch_notes (
        id            SERIAL PRIMARY KEY,
        patch_version TEXT NOT NULL,
        champion_key  TEXT NOT NULL,
        change_type   TEXT NOT NULL CHECK (change_type IN ('buff', 'nerf', 'change')),
        ability_slot  TEXT,
        ability_name  TEXT,
        notes         JSONB,
        scraped_at    TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (patch_version, champion_key, ability_slot)
    );
    CREATE INDEX IF NOT EXISTS idx_pn_champ ON patch_notes(champion_key);
    CREATE INDEX IF NOT EXISTS idx_pn_patch ON patch_notes(patch_version);
"""

import os, sys, re, json, time, requests, psycopg2
from bs4 import BeautifulSoup
from psycopg2.extras import Json
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Update this URL every two weeks. Format is always consistent.
PATCH_URL = "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-8-notes/"
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def extract_patch_version(url):
    """Extracts '26.8' from the URL slug."""
    match = re.search(r'patch-(\d+)-(\d+)-notes', url)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return "unknown"

def classify_slot(title_text):
    """Maps ability title like 'W - Rampant Growth' to a slot key."""
    t = title_text.strip().upper()
    if t.startswith("PASSIVE"): return "passive"
    if t.startswith("Q"):       return "q"
    if t.startswith("W"):       return "w"
    if t.startswith("E"):       return "e"
    if t.startswith("R"):       return "r"
    return "base"  # base stats / general changes

def classify_change_type(ability_blocks):
    """
    Determine overall buff/nerf/change for a champion.
    Riot uses:
      - .attribute-change-item--positive  (green = buff)
      - .attribute-change-item--negative  (red = nerf)
      - no class modifier                 (neutral = change)
    """
    positives = 0
    negatives = 0
    for block in ability_blocks:
        positives += len(block['notes']) - sum(1 for n in block['notes'] if n.get('is_negative'))
        negatives += sum(1 for n in block['notes'] if n.get('is_negative'))
    # Fallback: keyword scan if no CSS hints
    if positives == 0 and negatives == 0:
        return 'change'
    if negatives == 0:
        return 'buff'
    if positives == 0:
        return 'nerf'
    # Mixed — whoever dominates
    return 'nerf' if negatives >= positives else 'buff'

def scrape():
    print(f"Fetching {PATCH_URL} ...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    res = requests.get(PATCH_URL, headers=headers, timeout=15)
    if res.status_code != 200:
        print(f"[!] HTTP {res.status_code} — aborting.")
        sys.exit(1)

    patch_version = extract_patch_version(PATCH_URL)
    print(f"Patch version: {patch_version}")

    soup = BeautifulSoup(res.text, "html.parser")

    # ── Find champion change blocks ───────────────────────────────────────────
    # Riot's page structure uses .patch-change-block for each champion section.
    # We look for any block that has a readable champion title.
    champ_blocks = soup.find_all("div", class_=re.compile(r"patch-change-block"))
    if not champ_blocks:
        # Fallback: look for article sections
        champ_blocks = soup.find_all("section", class_=re.compile(r"change"))

    print(f"Found {len(champ_blocks)} change blocks.")
    results = []

    for block in champ_blocks:
        # Champion name — in h3.change-title or first h3/h4 in block
        title_tag = (
            block.find(class_=re.compile(r"change-title")) or
            block.find(["h3", "h4"])
        )
        if not title_tag:
            continue

        champ_name = title_tag.get_text(strip=True)
        # Skip non-champion sections (items, systems, etc.) — they won't match DDragon
        if len(champ_name) > 40 or not champ_name[0].isupper():
            continue

        # Normalize to DDragon key format (no spaces, e.g. "Twisted Fate" → "TwistedFate")
        champ_key = champ_name.replace(" ", "").replace("'", "").replace(".", "")

        ability_blocks = []

        # ── Find ability sub-sections ─────────────────────────────────────────
        # Each ability is in a container with a title li/div and change li items.
        # Riot uses multiple structures across patches; we try all of them.
        ability_sections = (
            block.find_all(class_=re.compile(r"attribute-change-detail")) or
            block.find_all("ul", class_=re.compile(r"content-border|patch-change-block-list")) or
            []
        )

        if not ability_sections:
            # Try generic: find all <li> or <div> with a bolded ability name
            # and collect sibling bullets
            all_lis = block.find_all("li")
            current_ability = {"slot": "base", "name": "Base Stats", "notes": []}
            for li in all_lis:
                text = li.get_text(strip=True)
                # Detect ability title lines: start with Q/W/E/R/Passive and a dash
                if re.match(r'^[QWER]\s*[-–]|^Passive\s*[-–]|^Base Stats', text, re.I):
                    if current_ability["notes"]:
                        ability_blocks.append(current_ability)
                    slot = classify_slot(text)
                    current_ability = {"slot": slot, "name": text, "notes": []}
                elif text and text != champ_name:
                    # Is it a buff or nerf? Check CSS class
                    is_pos = bool(li.get("class") and any("positive" in c for c in li.get("class", [])))
                    is_neg = bool(li.get("class") and any("negative" in c for c in li.get("class", [])))
                    if not is_pos and not is_neg:
                        # Keyword fallback
                        low = text.lower()
                        is_pos = any(w in low for w in ["increased", "added", "new", "improved", "gained", "restored", "now also"])
                        is_neg = any(w in low for w in ["reduced", "decreased", "removed", "lowered", "no longer", "lost"])
                    current_ability["notes"].append({"text": text, "is_positive": is_pos, "is_negative": is_neg})
            if current_ability["notes"]:
                ability_blocks.append(current_ability)
        else:
            for section in ability_sections:
                # Ability name
                title_el = (
                    section.find(class_=re.compile(r"attribute-change-title|patch-change-block-title")) or
                    section.find(["h4", "strong", "b"])
                )
                ability_title = title_el.get_text(strip=True) if title_el else "Base Stats"
                slot = classify_slot(ability_title)

                notes = []
                for li in section.find_all("li", class_=re.compile(r"attribute-change-item|patch-change-item")):
                    text = li.get_text(strip=True)
                    if not text: continue
                    classes = li.get("class", [])
                    is_pos = any("positive" in c for c in classes)
                    is_neg = any("negative" in c for c in classes)
                    if not is_pos and not is_neg:
                        low = text.lower()
                        is_pos = any(w in low for w in ["increased", "added", "new", "improved", "gained", "restored", "now also"])
                        is_neg = any(w in low for w in ["reduced", "decreased", "removed", "lowered", "no longer", "lost"])
                    notes.append({"text": text, "is_positive": is_pos, "is_negative": is_neg})

                # Also pick up plain <li> children (some patches skip the class)
                if not notes:
                    for li in section.find_all("li"):
                        text = li.get_text(strip=True)
                        if not text or text == ability_title: continue
                        low = text.lower()
                        is_pos = any(w in low for w in ["increased", "added", "new", "improved", "gained"])
                        is_neg = any(w in low for w in ["reduced", "decreased", "removed", "lowered", "no longer"])
                        notes.append({"text": text, "is_positive": is_pos, "is_negative": is_neg})

                if notes:
                    ability_blocks.append({"slot": slot, "name": ability_title, "notes": notes})

        if not ability_blocks:
            continue

        change_type = classify_change_type(ability_blocks)
        results.append({
            "champion_key":  champ_key,
            "change_type":   change_type,
            "ability_blocks": ability_blocks
        })
        print(f"  [{change_type.upper():6}] {champ_key} — {len(ability_blocks)} ability section(s)")

    if not results:
        print("[!] No champion changes found. The page structure may have changed.")
        print("    Open the URL in a browser and inspect the HTML, then update the selectors above.")
        sys.exit(1)

    # ── Write to DB ───────────────────────────────────────────────────────────
    conn   = get_db()
    cursor = conn.cursor()
    total  = 0

    for champ in results:
        for ab in champ["ability_blocks"]:
            cursor.execute("""
                INSERT INTO patch_notes (patch_version, champion_key, change_type, ability_slot, ability_name, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (patch_version, champion_key, ability_slot) DO UPDATE SET
                    change_type  = EXCLUDED.change_type,
                    ability_name = EXCLUDED.ability_name,
                    notes        = EXCLUDED.notes,
                    scraped_at   = NOW();
            """, (
                patch_version,
                champ["champion_key"],
                champ["change_type"],
                ab["slot"],
                ab["name"],
                Json(ab["notes"])
            ))
            total += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\n[✓] Done — {len(results)} champions, {total} ability rows stored for patch {patch_version}.")

if __name__ == "__main__":
    scrape()