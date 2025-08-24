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
        # This loop automatically finds and loads all cog files
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"Loaded cog: {filename}")

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        print(f'Bot is ready and running in {len(self.guilds)} servers.')
        print('--------------------------------')

bot = PetBot()
setup_database()
bot.run(TOKEN)