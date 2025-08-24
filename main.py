# main.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Import our database setup function
from database import setup_database

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Load the commands cog
bot.load_extension('commands')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print(f'Bot is ready and running in {len(bot.guilds)} servers.')
    print('--------------------------------')

# Run the setup and the bot
setup_database()
bot.run(TOKEN)