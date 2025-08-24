import discord
from discord.ext import commands, tasks
import datetime
import random
import os                  # New import for operating system functions
from dotenv import load_dotenv # New import to load .env file

load_dotenv() # This loads the variables from your .env file

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Pet Data Storage ---
pets = {}

# --- Background Task ---
@tasks.loop(minutes=5)
async def stat_decay_loop():
    await bot.wait_until_ready()
    
    user_ids = list(pets.keys())
    
    for user_id in user_ids:
        pet = pets[user_id]
        # Stat decay values are now slightly adjusted
        pet['hunger'] = max(0, pet['hunger'] - 2)
        pet['happiness'] = max(0, pet['happiness'] - 1)
        # Add decay for the new cleanliness stat
        pet['cleanliness'] = max(0, pet['cleanliness'] - 3)
        
    print("Stat decay loop has run for all pets.")

# --- Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print('Bot is ready to hatch some pets!')
    print('--------------------------------')
    stat_decay_loop.start()

# --- Bot Commands ---
@bot.command(name='hatch')
async def hatch_pet(ctx):
    """Allows a user to hatch a new pet."""
    user_id = ctx.author.id
    if user_id in pets:
        await ctx.send("You already have a pet! You can't hatch another one.")
    else:
        # Added 'cleanliness' to the initial pet data
        pets[user_id] = {
            'name': 'Pet',
            'born_at': datetime.datetime.now(),
            'hunger': 100,
            'happiness': 100,
            'cleanliness': 100, # New stat
            'money': 10
        }
        user_name = ctx.author.display_name
        await ctx.send(f"Congratulations, {user_name}! You've hatched a new virtual pet! 🎉 You also find 10 coins to start with!")

@bot.command(name='status')
async def check_status(ctx):
    """Checks the status of the user's pet."""
    user_id = ctx.author.id
    if user_id not in pets:
        await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
        return

    pet = pets[user_id]
    age_delta = datetime.datetime.now() - pet['born_at']
    total_seconds = int(age_delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Updated to display the cleanliness stat
    status_message = (
        f"**{pet['name']}'s Status**\n"
        f"-----------------\n"
        f"❤️ Happiness: {pet['happiness']}/100\n"
        f"🍔 Hunger: {pet['hunger']}/100\n"
        f"✨ Cleanliness: {pet['cleanliness']}/100\n"
        f"💰 Coins: {pet['money']}\n"
        f"🎂 Age: {hours}h {minutes}m {seconds}s"
    )
    await ctx.send(status_message)

@bot.command(name='feed')
async def feed_pet(ctx):
    """Feeds the user's pet to restore hunger."""
    user_id = ctx.author.id
    if user_id not in pets:
        await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
        return

    pet = pets[user_id]
    pet['hunger'] = min(100, pet['hunger'] + 15)
    await ctx.send(f"You fed your pet! 🍔 Its hunger is now {pet['hunger']}/100.")

@bot.command(name='play')
async def play_with_pet(ctx):
    """Play with your pet to increase happiness and earn coins."""
    user_id = ctx.author.id
    if user_id not in pets:
        await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
        return

    pet = pets[user_id]
    pet['happiness'] = min(100, pet['happiness'] + 20)
    money_earned = random.randint(5, 15)
    pet['money'] += money_earned
    await ctx.send(f"You played with your pet! ❤️ Its happiness is now {pet['happiness']}/100. You also earned {money_earned} coins! 💰")

# --- NEW COMMAND ---
@bot.command(name='clean')
async def clean_pet(ctx):
    """Cleans your pet to restore its cleanliness."""
    user_id = ctx.author.id
    if user_id not in pets:
        await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
        return
        
    pet = pets[user_id]
    pet['cleanliness'] = 100 # A full clean restores it completely
    await ctx.send("You cleaned your pet! ✨ It's sparkling clean now.")

# --- Run the Bot ---
# The old line was: bot.run('YOUR_BOT_TOKEN_HERE')
# The new line loads the token from the environment variable
bot.run(os.getenv('TOKEN'))