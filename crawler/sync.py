import os
import time
import json
import requests
from dotenv import load_dotenv

# Load your Riot API key from the .env file
load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")
print(f"DEBUG: My API Key is -> {API_KEY}") # ADD THIS LINE
HEADERS = {"X-Riot-Token": API_KEY}

# Hardcode 3 known pro/streamer accounts (GameName, TagLine)
PRO_ACCOUNTS = [
    {"name": "G2 Jankos", "tag": "unc2"},
    {"name": "Caps", "tag": "EUW"},
    {"name": "Rekkles", "tag": "EUW"}
]

def generate_pro_list():
    valid_pros = []
    
    for pro in PRO_ACCOUNTS:
        print(f"Extracting PUUID for {pro['name']}#{pro['tag']}...")
        
        # Account-V1 Endpoint (Global routing: americas, asia, europe)
        # For Accounts, Riot recommends routing to the closest global region. We will use 'europe' as a default global router.
        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{pro['name']}/{pro['tag']}"
        
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            valid_pros.append({
                "riot_id": f"{data['gameName']}#{data['tagLine']}",
                "puuid": data['puuid']
            })
        else:
            print(f"Failed to fetch {pro['name']}: HTTP {response.status_code}")
        
        # Strict rate limiting: Riot dev keys allow 20 requests per second, but let's be safe.
        time.sleep(1.2)
        
    with open("pros_list.json", "w") as f:
        json.dump(valid_pros, f, indent=4)
        
    print("Extraction complete. Check pros_list.json.")

if __name__ == "__main__":
    generate_pro_list()