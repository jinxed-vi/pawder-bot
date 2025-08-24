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
class PetBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)

    # This is the new, correct way to load cogs
    async def setup_hook(self):
        await self.load_extension('commands')

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        print(f'Bot is ready and running in {len(self.guilds)} servers.')
        print('--------------------------------')

# Create an instance of our bot
bot = PetBot()

# Run the setup and the bot
setup_database()
bot.run(TOKEN)