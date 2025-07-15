import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv
import redis
import json

# Assuming the downloader and config are in the same project
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Configuration ---
load_dotenv()
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ARL_COOKIE = os.environ.get("DEEZER_ARL_COOKIE")
REDIS_URL = os.environ.get("REDIS_URL")

if not all([DISCORD_TOKEN, ARL_COOKIE, REDIS_URL]):
    logging.error("CRITICAL: DISCORD_TOKEN, DEEZER_ARL_COOKIE, and REDIS_URL must be set in .env file.")
    exit()

# --- Bot and Services Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'discord_downloads')
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Connect to Redis
redis_client = redis.from_url(REDIS_URL)

# --- Helper Functions ---
def get_queue_key(guild_id):
    return f"discord_queue:{guild_id}"

def cleanup_file(file_path):
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logging.error(f"Error cleaning up file {file_path}: {e}")

# --- Core Playback Logic ---
async def play_next_in_queue(ctx):
    guild_id = ctx.guild.id
    queue_key = get_queue_key(guild_id)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        return # Already playing, do nothing

    # Get next song from Redis queue (FIFO)
    song_data_json = redis_client.rpop(queue_key)

    if song_data_json:
        song_data = json.loads(song_data_json)
        file_path = song_data['path']
        title = song_data['title']

        if not os.path.exists(file_path):
            await ctx.send(f"Oops, couldn't find the file for '{title}'. Skipping.")
            # Recursively call to try the next song
            await play_next_in_queue(ctx)
            return

        def after_playing(error):
            if error:
                logging.error(f'Error after playing: {error}')
            cleanup_file(file_path)
            # Use call_soon_threadsafe to schedule the async func from a sync context
            bot.loop.call_soon_threadsafe(asyncio.create_task, play_next_in_queue(ctx))

        await ctx.send(f"Now playing: {title}")
        voice_client.play(discord.FFmpegPCMAudio(file_path), after=after_playing)
    else:
        await ctx.send("Queue finished. Disconnecting in a moment.")
        await asyncio.sleep(5)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()

# --- Bot Commands ---
@bot.event
async def on_ready():
    logging.info(f'Bot logged in as {bot.user}')

@bot.command(name='p')
async def play(ctx, *, song_name: str):
    """Searches for a song, adds it to the queue, and starts playing."""
    if not ctx.author.voice:
        await ctx.send("Please join a voice channel first.")
        return

    await ctx.send(f"Searching for '{song_name}'...")

    config = DeezerConfig(cookie_arl=ARL_COOKIE, download_folder=DOWNLOADS_DIR)
    client = DeezerClient(config=config)
    client.initialize()

    track_id = client.search_track(song_name)
    if not track_id:
        await ctx.send(f"Sorry, I couldn't find any song matching '{song_name}'.")
        return

    await ctx.send(f"Found it! Downloading now...")
    try:
        file_path, filename = client.download_track(track_id)
    except Exception as e:
        await ctx.send(f"An error occurred while downloading: {e}")
        return

    # Add to Redis queue (FIFO)
    queue_key = get_queue_key(ctx.guild.id)
    song_data = json.dumps({'path': file_path, 'title': filename})
    redis_client.lpush(queue_key, song_data)

    await ctx.send(f"Added to queue: {filename}")

    # Connect to voice and start playing if not already
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        channel = ctx.author.voice.channel
        await channel.connect()
    
    if not (voice_client and (voice_client.is_playing() or voice_client.is_paused())):
        await play_next_in_queue(ctx)

@bot.command(name='s')
async def skip(ctx):
    """Skips the current song and plays the next in the queue."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        await ctx.send("Skipping...")
        voice_client.stop() # This will trigger the 'after' callback and play the next song
    else:
        await ctx.send("I'm not playing anything right now.")

@bot.command(name='q')
async def view_queue(ctx):
    """Displays the current song queue."""
    queue_key = get_queue_key(ctx.guild.id)
    queued_songs_json = redis_client.lrange(queue_key, 0, -1)
    
    if not queued_songs_json:
        await ctx.send("The queue is currently empty.")
        return

    embed = discord.Embed(title="Song Queue", color=discord.Color.blue())

    song_list = []
    # Redis lrange returns items from right to left, so we reverse to show the correct FIFO order.
    for song_json in reversed(queued_songs_json):
        song_data = json.loads(song_json)
        filename = song_data['title']
        clean_title, _ = os.path.splitext(filename)
        song_list.append(clean_title)
    
    embed.description = "\n".join(f"{i+1}. {title}" for i, title in enumerate(song_list))
    await ctx.send(embed=embed)

@bot.command(name='stop')
async def stop(ctx):
    """Stops the music, clears the queue, and disconnects the bot."""
    queue_key = get_queue_key(ctx.guild.id)
    redis_client.delete(queue_key)

    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        await voice_client.disconnect()
        await ctx.send("Music stopped, queue cleared, and disconnected.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

if __name__ == '__main__':
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN, log_handler=None)
    else:
        print("Discord token not found. Please set it in the .env file.")
