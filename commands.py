# commands.py
import discord
from discord.ext import commands, tasks
import datetime
import random
from collections import Counter

# Import our database context manager
from database import get_db_cursor

# Define constants here
SHOP_ITEMS = { "apple": {"name": "Apple 🍎", "price": 10, "description": "Restores 25 hunger.", "effect": {"stat": "hunger", "value": 25}}, "bread": {"name": "Bread 🍞", "price": 20, "description": "Restores 40 hunger.", "effect": {"stat": "hunger", "value": 40}}, "toy": {"name": "Squeaky Toy 🧸", "price": 30, "description": "Restores 35 happiness.", "effect": {"stat": "happiness", "value": 35}}, "soap": {"name": "Soap Bar 🧼", "price": 15, "description": "Restores 50 cleanliness.", "effect": {"stat": "cleanliness", "value": 50}}}
PRIZE_ITEMS = ("apple", "bread", "toy", "soap")

class PetCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stat_decay_loop.start() # Start the background task

    # The background task is now part of the Cog
    @tasks.loop(minutes=5)
    async def stat_decay_loop(self):
        with get_db_cursor() as cur:
            cur.execute('''
                UPDATE pets SET 
                    hunger = MAX(0, hunger - 2), 
                    happiness = MAX(0, happiness - 1), 
                    cleanliness = MAX(0, cleanliness - 3)
            ''')
        print("Database stat decay loop has run.")
        
    @stat_decay_loop.before_loop
    async def before_stat_decay_loop(self):
        await self.bot.wait_until_ready() # Wait for the bot to be ready

    # All commands are now defined with @commands.command()
    # and take 'self' as the first argument
    @commands.command(name='hatch')
    async def hatch_pet(self, ctx):
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (user_id,))
            if cur.fetchone():
                await ctx.send("You already have a pet!")
            else:
                cur.execute("INSERT INTO pets (user_id, name, born_at, hunger, happiness, cleanliness, money) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (user_id, 'Pet', datetime.datetime.now().isoformat(), 100, 100, 100, 10))
                await ctx.send(f"Congratulations, {ctx.author.display_name}! You've hatched a new pet! 🎉 Use `!name <name>` to name it!")

    @commands.command(name='name')
    async def name_pet(self, ctx, *, new_name: str = None):
        user_id = ctx.author.id
        
        if new_name is None:
            await ctx.send("You need to provide a name! Usage: `!name <your_pet_name>`")
            return
            
        if not (0 < len(new_name) <= 25):
            await ctx.send("The name must be between 1 and 25 characters long.")
            return

        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET name = ? WHERE user_id = ?", (new_name, user_id))
            
            if cur.rowcount == 0:
                await ctx.send("You don't have a pet to name! Use `!hatch` first.")
            else:
                await ctx.send(f"You've named your pet **{new_name}**! 🎉")

    @commands.command(name='status')
    async def check_status(self, ctx ):
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,))
            pet = cur.fetchone()

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

    @commands.command(name='feed')
    async def feed_pet(self, ctx ):
        user_id = ctx.author.id
        
        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET hunger = MIN(100, hunger + 15) WHERE user_id = ?", (user_id,))
            
            if cur.rowcount == 0:
                await ctx.send("You don't have a pet to feed! Use `!hatch` first.")
            else:
                cur.execute("SELECT hunger FROM pets WHERE user_id = ?", (user_id,))
                new_hunger = cur.fetchone()[0]
                await ctx.send(f"You fed your pet! 🍔 Its hunger is now {new_hunger}/100.")

    @commands.command(name='play')
    async def play_with_pet(self, ctx ):
        user_id = ctx.author.id
        money_earned = random.randint(5, 15)
        
        with get_db_cursor() as cur:
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

    @commands.command(name='clean')
    async def clean_pet(self, ctx ):
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET cleanliness = 100 WHERE user_id = ?", (user_id,))
            
            if cur.rowcount == 0:
                await ctx.send("You don't have a pet to clean! Use `!hatch` first.")
            else:
                await ctx.send("You cleaned your pet! ✨ It's sparkling clean now.")

    @commands.command(name='shop')
    async def show_shop(self, ctx ):
        embed = discord.Embed(title="Pet Shop", description="Use `!buy <item_id>` to purchase an item.", color=discord.Color.gold())
        for item_id, item_details in SHOP_ITEMS.items():
            embed.add_field(name=f"{item_details['name']} - {item_details['price']} Coins", value=f"`{item_id}` - {item_details['description']}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='buy')
    async def buy_item(self, ctx , item_id: str = None):
        """Buys an item from the shop and adds it to your inventory."""
        if item_id is None:
            await ctx.send("You need to specify what to buy! Use `!buy <item_id>`.")
            return
            
        item_id = item_id.lower()
        if item_id not in SHOP_ITEMS:
            await ctx.send("That item doesn't exist in the shop.")
            return

        user_id = ctx.author.id
        item = SHOP_ITEMS[item_id]
        
        with get_db_cursor() as cur:
            cur.execute("SELECT money FROM pets WHERE user_id = ?", (user_id,))
            pet = cur.fetchone()
            
            if not pet:
                await ctx.send("You need to hatch a pet first with `!hatch`.")
                return
                
            if pet['money'] < item['price']:
                await ctx.send(f"You don't have enough money! You need {item['price']} coins but only have {pet['money']}.")
                return

            # Subtract money and add item to inventory
            new_money = pet['money'] - item['price']
            cur.execute("UPDATE pets SET money = ? WHERE user_id = ?", (new_money, user_id))
            cur.execute("INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)", (user_id, item_id))
            
            await ctx.send(f"You bought a {item['name']}! It has been added to your inventory. Use `!use {item_id}` to use it.")

    @commands.command(name='inventory', aliases=['inv'])
    async def show_inventory(self, ctx ):
        """Shows the items in your inventory."""
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("SELECT item_id FROM inventory WHERE owner_id = ?", (user_id,))
            # fetchall() returns a list of tuples, e.g., [('apple',), ('apple',), ('toy',)]
            items_in_db = cur.fetchall()
            
            if not items_in_db:
                await ctx.send("Your inventory is empty. Buy items from the `!shop`!")
                return
                
            # We extract the first element from each tuple to get a simple list of item IDs
            item_ids = [item[0] for item in items_in_db]
            # Counter creates a dictionary-like object with counts, e.g., {'apple': 2, 'toy': 1}
            item_counts = Counter(item_ids)
            
            embed = discord.Embed(title=f"{ctx.author.display_name}'s Inventory", color=discord.Color.orange())
            
            description = ""
            for item_id, count in item_counts.items():
                item_details = SHOP_ITEMS[item_id]
                description += f"{item_details['name']} **x{count}**\n"
                
            embed.description = description
            await ctx.send(embed=embed)


    @commands.command(name='use')
    async def use_item(self, ctx , item_id: str = None):
        """Uses an item from your inventory."""
        if item_id is None:
            await ctx.send("You need to specify what to use! Usage: `!use <item_id>`")
            return

        item_id = item_id.lower()
        if item_id not in SHOP_ITEMS:
            await ctx.send("That's not a valid item.")
            return

        user_id = ctx.author.id
        item_effect = SHOP_ITEMS[item_id]['effect']
        with get_db_cursor() as cur:
            # Check if the user has the item
            cur.execute("SELECT entry_id FROM inventory WHERE owner_id = ? AND item_id = ?", (user_id, item_id))
            item_to_use = cur.fetchone()
            
            if not item_to_use:
                await ctx.send(f"You don't have a {SHOP_ITEMS[item_id]['name']} in your inventory.")
                return

            # Apply the effect
            stat_to_change = item_effect['stat']
            value_to_add = item_effect['value']
            
            cur.execute(f"UPDATE pets SET {stat_to_change} = MIN(100, {stat_to_change} + ?) WHERE user_id = ?", (value_to_add, user_id))
            
            # Remove the item from inventory (using its unique entry_id)
            cur.execute("DELETE FROM inventory WHERE entry_id = ?", (item_to_use[0],))
            
            cur.execute(f"SELECT {stat_to_change} FROM pets WHERE user_id = ?", (user_id,))
            new_stat_value = cur.fetchone()[0]

            await ctx.send(f"You used a {SHOP_ITEMS[item_id]['name']}! Your pet's {stat_to_change} is now {new_stat_value}/100.")

    @commands.command(name='prize')
    async def claim_prize(self, ctx ):
        """Claims a daily prize of a random item."""
        user_id = ctx.author.id
        cooldown = datetime.timedelta(hours=24)
        with get_db_cursor() as cur:
            cur.execute("SELECT last_prize FROM pets WHERE user_id = ?", (user_id,))
            pet_data = cur.fetchone()
            
            if not pet_data:
                await ctx.send("You need to `!hatch` a pet before claiming a prize.")
                return

            last_claimed_str = pet_data['last_prize']
            
            if last_claimed_str:
                last_claimed_time = datetime.datetime.fromisoformat(last_claimed_str)
                time_since_claim = datetime.datetime.now() - last_claimed_time
                
                if time_since_claim < cooldown:
                    time_remaining = cooldown - time_since_claim
                    hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    await ctx.send(f"You've already claimed your prize. Please wait **{hours}h {minutes}m**.")
                    return

            # If cooldown is over, grant a random item prize
            won_item_id = random.choice(PRIZE_ITEMS)
            item_details = SHOP_ITEMS[won_item_id]
            current_time_str = datetime.datetime.now().isoformat()
            
            # Add the item to inventory and update the prize timestamp
            cur.execute("INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)", (user_id, won_item_id))
            cur.execute("UPDATE pets SET last_prize = ? WHERE user_id = ?", (current_time_str, user_id))
            
            await ctx.send(f"You claimed your daily prize and received a {item_details['name']}! It's now in your inventory.")
    
    # --- NEW COMMAND ---
    @commands.command(name='leaderboard', aliases=['lb'])
    async def show_leaderboard(self, ctx ):
        """Shows the top 10 richest pet owners."""
        with get_db_cursor() as cur:
            # The SQL query to get the top 10 users, sorted by money
            cur.execute("SELECT user_id, name, money FROM pets ORDER BY money DESC LIMIT 10")
            top_users = cur.fetchall()

        if not top_users:
            await ctx.send("There's no one on the leaderboard yet!")
            return

        embed = discord.Embed(title="💰 Top 10 Richest Pets", color=discord.Color.green())
        
        description = ""
        for rank, user_data in enumerate(top_users, start=1):
            # We need to fetch the Discord user object to get their current name
            # This is an API call, so it can be slow if the leaderboard is long
            user = self.bot.get_user(user_data['user_id'])
            if user:
                user_display_name = user.display_name
            else:
                user_display_name = "Unknown User" # If the user has left the server
                
            description += f"**{rank}.** {user_display_name}'s *{user_data['name']}* - {user_data['money']} Coins\n"

        embed.description = description
        await ctx.send(embed=embed)


# This setup function is required for the cog to be loaded
def setup(bot):
    bot.add_cog(PetCommands(bot))