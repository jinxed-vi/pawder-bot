import discord
from discord.ext import commands, tasks
import datetime
import random
import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()

# --- Database Setup ---
DB_FILE = "pets.db"

def setup_database():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pets (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            born_at TEXT NOT NULL,
            hunger INTEGER NOT NULL,
            happiness INTEGER NOT NULL,
            cleanliness INTEGER NOT NULL,
            money INTEGER NOT NULL
        )
    ''')
    con.commit()
    con.close()

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Shop ---
SHOP_ITEMS = {
    "apple": {
        "name": "Apple 🍎", "price": 10, "description": "Restores 25 hunger.",
        "effect": {"stat": "hunger", "value": 25}
    },
    "bread": {
        "name": "Bread 🍞", "price": 20, "description": "Restores 40 hunger.",
        "effect": {"stat": "hunger", "value": 40}
    },
    "toy": {
        "name": "Squeaky Toy 🧸", "price": 30, "description": "Restores 35 happiness.",
        "effect": {"stat": "happiness", "value": 35}
    },
     "soap": {
        "name": "Soap Bar 🧼", "price": 15, "description": "Restores 50 cleanliness.",
        "effect": {"stat": "cleanliness", "value": 50}
    }
}

# --- Background Task ---
@tasks.loop(minutes=5)
async def stat_decay_loop():
    await bot.wait_until_ready()
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute('''
        UPDATE pets 
        SET 
            hunger = MAX(0, hunger - 2), 
            happiness = MAX(0, happiness - 1), 
            cleanliness = MAX(0, cleanliness - 3)
    ''')
    con.commit()
    con.close()
    print("Database stat decay loop has run.")

# --- Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print('--------------------------------')
    stat_decay_loop.start()

# --- Bot Commands ---

@bot.command(name='hatch')
async def hatch_pet(ctx):
    user_id = ctx.author.id
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (user_id,))
    if cur.fetchone():
        await ctx.send("You already have a pet!")
    else:
        cur.execute("INSERT INTO pets VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, 'Pet', datetime.datetime.now().isoformat(), 100, 100, 100, 10))
        await ctx.send(f"Congratulations, {ctx.author.display_name}! You've hatched a new virtual pet! 🎉 Use `!name <pet_name>` to give it a name!")
    
    con.commit()
    con.close()

# --- NEW COMMAND ---
@bot.command(name='name')
async def name_pet(ctx, *, new_name: str = None):
    """Names or renames your pet."""
    user_id = ctx.author.id
    
    if new_name is None:
        await ctx.send("You need to provide a name! Usage: `!name <your_pet_name>`")
        return
        
    # Basic validation for the name
    if not (0 < len(new_name) <= 25):
        await ctx.send("The name must be between 1 and 25 characters long.")
        return

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    # The SQL query to update the name for the specific user
    cur.execute("UPDATE pets SET name = ? WHERE user_id = ?", (new_name, user_id))
    
    if cur.rowcount == 0:
        await ctx.send("You don't have a pet to name! Use `!hatch` first.")
    else:
        await ctx.send(f"You've named your pet **{new_name}**! 🎉")
    
    con.commit()
    con.close()

@bot.command(name='status')
async def check_status(ctx):
    user_id = ctx.author.id
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,))
    pet = cur.fetchone()
    con.close()

    if not pet:
        await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
        return

    born_at = datetime.datetime.fromisoformat(pet['born_at'])
    age_delta = datetime.datetime.now() - born_at
    total_seconds = int(age_delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    embed = discord.Embed(title=f"{pet['name']}'s Status", color=discord.Color.blue())
    embed.add_field(name="❤️ Happiness", value=f"{pet['happiness']}/100", inline=True)
    embed.add_field(name="🍔 Hunger", value=f"{pet['hunger']}/100", inline=True)
    embed.add_field(name="✨ Cleanliness", value=f"{pet['cleanliness']}/100", inline=True)
    embed.add_field(name="💰 Coins", value=pet['money'], inline=True)
    embed.add_field(name="🎂 Age", value=f"{hours}h {minutes}m {seconds}s", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name='feed')
async def feed_pet(ctx):
    user_id = ctx.author.id
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    cur.execute("UPDATE pets SET hunger = MIN(100, hunger + 15) WHERE user_id = ?", (user_id,))
    
    if cur.rowcount == 0:
        await ctx.send("You don't have a pet to feed! Use `!hatch` first.")
    else:
        cur.execute("SELECT hunger FROM pets WHERE user_id = ?", (user_id,))
        new_hunger = cur.fetchone()[0]
        await ctx.send(f"You fed your pet! 🍔 Its hunger is now {new_hunger}/100.")
        
    con.commit()
    con.close()


@bot.command(name='play')
async def play_with_pet(ctx):
    user_id = ctx.author.id
    money_earned = random.randint(5, 15)
    
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    cur.execute('''
        UPDATE pets 
        SET 
            happiness = MIN(100, happiness + 20), 
            money = money + ?
        WHERE user_id = ?
    ''', (money_earned, user_id))
    
    if cur.rowcount == 0:
        await ctx.send("You don't have a pet to play with! Use `!hatch` first.")
    else:
        cur.execute("SELECT happiness FROM pets WHERE user_id = ?", (user_id,))
        new_happiness = cur.fetchone()[0]
        await ctx.send(f"You played with your pet! ❤️ Its happiness is now {new_happiness}/100. You also earned {money_earned} coins! 💰")

    con.commit()
    con.close()


@bot.command(name='clean')
async def clean_pet(ctx):
    user_id = ctx.author.id
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    
    cur.execute("UPDATE pets SET cleanliness = 100 WHERE user_id = ?", (user_id,))
    
    if cur.rowcount == 0:
        await ctx.send("You don't have a pet to clean! Use `!hatch` first.")
    else:
        await ctx.send("You cleaned your pet! ✨ It's sparkling clean now.")
    
    con.commit()
    con.close()

@bot.command(name='shop')
async def show_shop(ctx):
    embed = discord.Embed(title="Pet Shop", description="Use `!buy <item_id>` to purchase an item.", color=discord.Color.gold())
    for item_id, item_details in SHOP_ITEMS.items():
        embed.add_field(name=f"{item_details['name']} - {item_details['price']} Coins", value=f"`{item_id}` - {item_details['description']}", inline=False)
    await ctx.send(embed=embed)


@bot.command(name='buy')
async def buy_item(ctx, *, item_id: str = None):
    if item_id is None:
        await ctx.send("You need to specify what to buy! Use `!buy <item_id>`.")
        return
        
    item_id = item_id.lower()
    if item_id not in SHOP_ITEMS:
        await ctx.send("That item doesn't exist in the shop.")
        return

    user_id = ctx.author.id
    item = SHOP_ITEMS[item_id]
    
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    
    cur.execute("SELECT money FROM pets WHERE user_id = ?", (user_id,))
    pet = cur.fetchone()
    
    if not pet:
        await ctx.send("You need to hatch a pet first with `!hatch`.")
        con.close()
        return
        
    if pet['money'] < item['price']:
        await ctx.send(f"You don't have enough money! You need {item['price']} coins but only have {pet['money']}.")
        con.close()
        return

    new_money = pet['money'] - item['price']
    stat_to_change = item['effect']['stat']
    value_to_add = item['effect']['value']
    
    cur.execute(f'''
        UPDATE pets
        SET
            money = ?,
            {stat_to_change} = MIN(100, {stat_to_change} + ?)
        WHERE user_id = ?
    ''', (new_money, value_to_add, user_id))
    
    cur.execute(f"SELECT {stat_to_change} FROM pets WHERE user_id = ?", (user_id,))
    new_stat_value = cur.fetchone()[0]

    await ctx.send(f"You bought a {item['name']}! Your pet's {stat_to_change} is now {new_stat_value}/100.")

    con.commit()
    con.close()


# --- Run the Bot ---
setup_database()
bot.run(os.getenv('TOKEN'))