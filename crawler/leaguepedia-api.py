import requests
import json

def fetch_pro_players():
    # The endpoint for Leaguepedia's Cargo API
    url = "https://lol.fandom.com/api.php"
    
    # We are writing a SQL-style query inside the params
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": "Players",
        "fields": "ID, NameFull, Country, Birthdate, Role, Team, Twitter, Twitch, Image",
        # Only fetch active players to save bandwidth
        "where": "IsRetired = 0 AND Role IS NOT NULL", 
        "limit": "100" # You can increase this up to 500 per request!
    }
    
    print("Fetching data from Leaguepedia Cargo API...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        players = []
        
        for item in data.get("cargoquery", []):
            player_data = item.get("title", {})
            
            # Leaguepedia stores images as filenames (e.g., "Faker_2023.jpg")
            # We convert this into a direct Special:FilePath URL to download it later
            image_filename = player_data.get("Image", "").replace(" ", "_")
            image_url = f"https://lol.fandom.com/wiki/Special:FilePath/{image_filename}" if image_filename else None
            
            player = {
                "riot_id": player_data.get("ID"), # Usually their current pro tag
                "real_name": player_data.get("NameFull"),
                "nationality": player_data.get("Country"),
                "birthday": player_data.get("Birthdate"),
                "role": player_data.get("Role"),
                "team": player_data.get("Team"),
                "socials": {
                    "Twitter": player_data.get("Twitter"),
                    "Twitch": player_data.get("Twitch")
                },
                "source_image_url": image_url
            }
            players.append(player)
            
        print(f"Successfully fetched {len(players)} players!")
        
        # Dump to your local DB seeder file
        with open("pro_players_db.json", "w", encoding="utf-8") as f:
            json.dump(players, f, indent=4, ensure_ascii=False)
            
        print("Saved to pro_players_db.json. Remember to download these images to your own server!")
    else:
        print(f"Failed to fetch data: HTTP {response.status_code}")

if __name__ == "__main__":
    fetch_pro_players()