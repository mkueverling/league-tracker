import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}

# Match-V5 requires regional routing. EUW accounts go to europe, NA to americas, KR to asia.
# For this script, we will hardcode 'europe' and test an EUW player.
REGION = "europe" 

def crawl_matches():
    # 1. Read the dimension data
    if not os.path.exists("pros_list.json"):
        print("pros_list.json not found. Run sync.py first.")
        return
        
    with open("pros_list.json", "r") as f:
        pros = json.load(f)
        
    if not pros:
        return
        
    # Grab the first pro in the list
    target_pro = pros[0]
    puuid = target_pro["puuid"]
    print(f"Crawling matches for: {target_pro['riot_id']}")

    # 2. Get Match IDs (Fetching the last 5 games)
    match_list_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=2"
    response = requests.get(match_list_url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Failed to fetch match list: HTTP {response.status_code} - {response.text}")
        return
        
    match_ids = response.json()
    print(f"Found Match IDs: {match_ids}")
    
    if not match_ids:
        print("No recent matches found for this player in this region.")
        return

    time.sleep(1.2) # Rate limit pacing

    # 3. Get Match Details (The heavy payload)
    first_match_id = match_ids[0]
    print(f"Fetching details for match: {first_match_id}")
    
    match_detail_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{first_match_id}"
    match_response = requests.get(match_detail_url, headers=HEADERS)
    
    if match_response.status_code == 200:
        match_data = match_response.json()
        
        # 4. Save the raw payload to analyze the structure
        with open("sample_match.json", "w") as f:
            json.dump(match_data, f, indent=4)
            
        print("Match data saved to sample_match.json. Open this file to inspect the 'participants' array.")
    else:
        print(f"Failed to fetch match details: HTTP {match_response.status_code}")

if __name__ == "__main__":
    crawl_matches()