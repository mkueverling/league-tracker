import os
import requests
import urllib.parse
from dotenv import load_dotenv, find_dotenv

# Load API key
load_dotenv(find_dotenv(), override=True)
API_KEY = os.getenv("RIOT_API_KEY")

def fetch_puuid():
    print("=== Riot PUUID Fetcher ===")
    if not API_KEY:
        print("[!] Warning: RIOT_API_KEY not found in .env file!")
        
    riot_id = input("Enter Riot ID (e.g. country#euw): ").strip()
    
    if not riot_id or '#' not in riot_id:
        print("[!] Invalid format. You must include the '#' symbol.")
        return
        
    game_name, tag_line = riot_id.split('#', 1)
    
    # URL encode the name and tag
    safe_name = urllib.parse.quote(game_name.strip())
    safe_tag = urllib.parse.quote(tag_line.strip())
    
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
    headers = {"X-Riot-Token": API_KEY}
    
    print(f"\nFetching PUUID for {game_name}#{tag_line}...")
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        print(f"\n[✓] SUCCESS!")
        print(f"Riot ID: {data.get('gameName')}#{data.get('tagLine')}")
        print(f"PUUID:   {data.get('puuid')}\n")
    else:
        print(f"\n[!] Error {res.status_code}: Player not found or API key expired.\n")

if __name__ == "__main__":
    fetch_puuid()
    input("Press Enter to exit...")