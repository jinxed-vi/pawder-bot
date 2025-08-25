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

class MyHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Pawder Bot Help", 
            description="Here are all the available commands, grouped by category.",
            color=discord.Color.blurple()
        )
        
        for cog, cog_commands in mapping.items():
            if cog:
                filtered_commands = await self.filter_commands(cog_commands)
                if filtered_commands:
                    command_signatures = [f"`!{c.name}` - {c.short_doc}" for c in filtered_commands]
                    embed.add_field(
                        name=cog.qualified_name,
                        value="\n".join(command_signatures),
                        inline=False
                    )

        embed.set_footer(text="Use !help <command> for more info on a specific command.")
        await self.get_destination().send(embed=embed)

class PetBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents, help_command=MyHelpCommand())

    async def setup_hook(self):
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