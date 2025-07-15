import discord
from discord.ext import commands
import os
import asyncio
import re
import logging
from dotenv import load_dotenv

# Assuming the downloader and config are in the same project
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Configuration ---
load_dotenv()
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ARL_COOKIE = os.environ.get("DEEZER_ARL_COOKIE")

if not DISCORD_TOKEN or not ARL_COOKIE:
    logging.error("CRITICAL: DISCORD_TOKEN and DEEZER_ARL_COOKIE must be set in .env file.")
    exit()

# --- Bot and Directories Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'discord_downloads')
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# --- Helper Functions ---
def parse_deezer_url(url):
    """Parses a Deezer URL to extract content type and ID."""
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(track)/(\d+)', url)
    if not url_match:
        return None, None
    return url_match.groups() # ('track', '12345')

def cleanup_file(file_path):
    """Removes a file if it exists."""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logging.error(f"Error cleaning up file {file_path}: {e}")

# --- Music Playing Logic ---
async def download_song(url):
    """Downloads a song from Deezer and returns the file path."""
    content_type, content_id = parse_deezer_url(url)
    if not content_type or content_type != 'track':
        logging.warning(f"Unsupported Deezer URL for download: {url}")
        return None, "Please provide a valid Deezer track URL."

    logging.info(f"Starting download for: {content_type}/{content_id}")

    config = DeezerConfig(cookie_arl=ARL_COOKIE, download_folder=DOWNLOADS_DIR)
    client = DeezerClient(config=config)
    client.initialize()

    try:
        # We are only handling single tracks
        downloaded_file_paths = client.download_track(content_id)
        if not downloaded_file_paths:
            return None, "Could not download the track. It might be unavailable."
        
        # Return the path of the first (and only) downloaded file
        return downloaded_file_paths[0], None
    except DeezerException as e:
        logging.error(f"A Deezer error occurred: {e}")
        return None, f"A Deezer error occurred: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred during download: {e}")
        return None, "An unexpected error occurred."

@bot.event
async def on_ready():
    logging.info(f'Bot logged in as {bot.user}')

@bot.command(name='play')
async def play(ctx, url: str):
    """Plays a song from a Deezer track URL."""
    # Check if the user is in a voice channel
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return

    channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # Connect to the voice channel if not already connected
    if voice_client is None:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    if voice_client.is_playing() or voice_client.is_paused():
        await ctx.send("I'm already playing a song. Please wait for it to finish.")
        return

    await ctx.send(f"Got it! Downloading your song now...")

    # Download the song
    file_path, error_msg = await download_song(url)

    if error_msg:
        await ctx.send(error_msg)
        return

    if not file_path or not os.path.exists(file_path):
        await ctx.send("Something went wrong and the file could not be found after download.")
        return

    # Play the song
    await ctx.send(f"Now playing: {os.path.basename(file_path)}")
    try:
        voice_client.play(
            discord.FFmpegPCMAudio(file_path),
            after=lambda e: cleanup_file(file_path)
        )
    except Exception as e:
        await ctx.send(f"Error playing file: {e}")
        cleanup_file(file_path) # Clean up even if playback fails to start

@bot.command(name='stop')
async def stop(ctx):
    """Stops the music and disconnects the bot."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("Music stopped and disconnected.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

if __name__ == '__main__':
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Discord token not found. Please set it in the .env file.")
