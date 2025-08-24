import random
from typing import Counter
import discord
from discord.ext import commands, tasks
import datetime
from database import fetch_shop_item, get_db_cursor, fetch_pet, modify_pet_stat

class PetCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stat_decay_loop.start()

    def _get_pet_mood(self, pet):
        """Determines a pet's mood based on its stats."""
        # Calculate an average of the primary care stats
        avg_stats = (pet['hunger'] + pet['happiness'] + pet['cleanliness']) / 3

        if pet['willpower'] < 30 or avg_stats < 25:
            return "Neglected 😥"
        if pet['hunger'] < 40:
            return "Starving 😫"
        if pet['happiness'] < 40:
            return "Gloomy 😞"
        if pet['cleanliness'] < 40:
            return "Grubby 😒"
        if avg_stats < 85:
            return "Content 😐"
        
        return "Joyful 😊"

    @tasks.loop(minutes=5)
    async def stat_decay_loop(self):
        with get_db_cursor() as cur:
            # Step 1: Regular stat decay for all pets
            cur.execute('''
                UPDATE pets SET 
                    hunger = MAX(0, hunger - 2), 
                    happiness = MAX(0, happiness - 1), 
                    cleanliness = MAX(0, cleanliness - 3)
            ''')

            # Step 2: Decrease Willpower for neglected pets (stats at 0)
            cur.execute('''
                UPDATE pets SET willpower = MAX(0, willpower - 5)
                WHERE hunger = 0 OR happiness = 0 OR cleanliness = 0
            ''')

            # Step 3: Find any pets whose willpower has hit 0
            cur.execute("SELECT user_id, name FROM pets WHERE willpower <= 0")
            pets_to_remove = cur.fetchall()

            for pet in pets_to_remove:
                user_id = pet['user_id']
                pet_name = pet['name']

                # Step 4: Delete the pet and its inventory
                cur.execute("DELETE FROM pets WHERE user_id = ?", (user_id,))
                cur.execute("DELETE FROM inventory WHERE owner_id = ?", (user_id,))

                # Step 5: Try to send a DM to the user
                try:
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"You neglected your pet, **{pet_name}**, for too long. It has lost all its Willpower and run away. 😥")
                except discord.HTTPException:
                    print(f"Failed to send DM to user {user_id}. They might have DMs disabled.")
        
        print("Database stat decay and neglect loop has run.")
        
    @stat_decay_loop.before_loop
    async def before_stat_decay_loop(self):
        await self.bot.wait_until_ready() # Wait for the bot to be ready

    @commands.command(name='hatch')
    async def hatch_pet(self, ctx):
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (user_id,))
            if cur.fetchone():
                await ctx.send("You already have a pet!")
            else:
                cur.execute("INSERT INTO pets (user_id, name, born_at, hunger, happiness, cleanliness, money, willpower) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (user_id, 'Pet', datetime.datetime.now().isoformat(), 100, 100, 100, 10, 100))
                await ctx.send(f"Congratulations, {ctx.author.display_name}! You've hatched a new pet! 🎉")

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
    async def check_status(self, ctx):
        pet = fetch_pet(ctx.author.id)
        if not pet:
            await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
            return

        born_at = datetime.datetime.fromisoformat(pet['born_at'])
        age_delta = datetime.datetime.now() - born_at
        hours, remainder = divmod(int(age_delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        
        mood = self._get_pet_mood(pet)
        
        embed = discord.Embed(title=f"{pet['name']}'s Status", color=discord.Color.blue())
        embed.add_field(name="🎭 Mood", value=mood, inline=True)
        embed.add_field(name="💪 Willpower", value=f"{pet['willpower']}/100", inline=True)
        embed.add_field(name="❤️ Happiness", value=f"{pet['happiness']}/100", inline=True)
        embed.add_field(name="🍔 Hunger", value=f"{pet['hunger']}/100", inline=True)
        embed.add_field(name="✨ Cleanliness", value=f"{pet['cleanliness']}/100", inline=True)
        embed.add_field(name="💰 Coins", value=pet['money'], inline=True)
        embed.add_field(name="🎂 Age", value=f"{hours}h {minutes}m", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='feed')
    async def feed_pet(self, ctx):
        user_id = ctx.author.id
        cooldown = datetime.timedelta(hours=1)

        pet = fetch_pet(user_id)
        if not pet:
            await ctx.send("You don't have a pet to feed!")
            return
            
        last_fed_str = pet['last_feed']
        if last_fed_str:
            last_fed_time = datetime.datetime.fromisoformat(last_fed_str)
            if datetime.datetime.now() - last_fed_time < cooldown:
                time_remaining = cooldown - (datetime.datetime.now() - last_fed_time)
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                await ctx.send(f"Your pet is still full. You can feed it again in **{minutes}m {seconds}s**.")
                return

        new_hunger = modify_pet_stat(user_id, 'hunger', 15)
        modify_pet_stat(user_id, 'willpower', 1)
        
        # Update the timestamp
        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET last_feed = ? WHERE user_id = ?", (datetime.datetime.now().isoformat(), user_id))
        
        await ctx.send(f"You fed your pet! 🍔 Its hunger is now {new_hunger}/100.")
    
    @commands.command(name='play')
    async def play_with_pet(self, ctx):
        user_id = ctx.author.id
        cooldown = datetime.timedelta(hours=1)
        
        pet = fetch_pet(user_id)
        if not pet:
            await ctx.send("You don't have a pet to play with!")
            return

        last_played_str = pet['last_play']
        if last_played_str:
            last_played_time = datetime.datetime.fromisoformat(last_played_str)
            time_since_play = datetime.datetime.now() - last_played_time
            
            if time_since_play < cooldown:
                time_remaining = cooldown - time_since_play
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                await ctx.send(f"Your pet is tired! You can play again in **{minutes}m {seconds}s**.")
                return

        money_earned = random.randint(5, 15)
        new_happiness = modify_pet_stat(user_id, 'happiness', 20)
        modify_pet_stat(user_id, 'money', money_earned)
        modify_pet_stat(user_id, 'willpower', 1)
        
        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET last_play = ? WHERE user_id = ?", (datetime.datetime.now().isoformat(), user_id))

        await ctx.send(f"You played with your pet! ❤️ Its happiness is now {new_happiness}/100. You also earned {money_earned} coins! 💰")

    @commands.command(name='clean')
    async def clean_pet(self, ctx):
        user_id = ctx.author.id
        cooldown = datetime.timedelta(hours=1)

        pet = fetch_pet(user_id)
        if not pet:
            await ctx.send("You don't have a pet to clean!")
            return

        last_cleaned_str = pet['last_clean']
        if last_cleaned_str:
            last_cleaned_time = datetime.datetime.fromisoformat(last_cleaned_str)
            if datetime.datetime.now() - last_cleaned_time < cooldown:
                time_remaining = cooldown - (datetime.datetime.now() - last_cleaned_time)
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                await ctx.send(f"Your pet is already clean. You can clean it again in **{minutes}m {seconds}s**.")
                return

        modify_pet_stat(user_id, 'cleanliness', 100, mode='set')
        modify_pet_stat(user_id, 'willpower', 1)

        # Update the timestamp
        with get_db_cursor() as cur:
            cur.execute("UPDATE pets SET last_clean = ? WHERE user_id = ?", (datetime.datetime.now().isoformat(), user_id))
            
        await ctx.send("You cleaned your pet! ✨ It's sparkling clean now.")

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
                item_data = fetch_shop_item(item_id)
                if not item_data:
                    await ctx.send(f"Error: Item with ID `{item_id}` not found.")
                    return
                description += f"{item_data['name']} **x{count}**\n"
                
            embed.description = description
            await ctx.send(embed=embed)

    @commands.command(name='use')
    async def use_item(self, ctx , item_id: str = None):
        """Uses an item from your inventory."""
        if item_id is None:
            await ctx.send("You need to specify what to use! Usage: `!use <item_id>`")
            return

        item_id = item_id.lower()
        item = fetch_shop_item(item_id)
        if not item:
            await ctx.send("That item doesn't exist in the shop.")
            return

        user_id = ctx.author.id
        
        new_stat_value = modify_pet_stat(user_id, item['effect_stat'], item['effect_value'])
        modify_pet_stat(user_id, 'willpower', 2)

        # Remove item from inventory
        with get_db_cursor() as cur:
             cur.execute("DELETE FROM inventory WHERE owner_id = ? AND item_id = ? LIMIT 1", (user_id, item_id))
        
        await ctx.send(f"You used a {item['name']}! Your pet's {item['effect_stat']} is now {new_stat_value}/100.")


async def setup(bot):
    await bot.add_cog(PetCommands(bot))