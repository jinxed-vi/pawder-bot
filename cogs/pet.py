import random
from typing import Counter
import discord
from discord.ext import commands, tasks
import datetime
from database import (
    fetch_shop_item,
    get_db_cursor,
    fetch_pet,
    get_stat_definition_id,
    modify_pet_stat,
)
from utils import Pet


class PetCommands(commands.Cog, name="🐶 Pet Commands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stat_decay_loop.start()

    def _get_pet_mood(self, pet: Pet):
        """Determines a pet's mood based on its stats."""
        # Calculate an average of the primary care stats
        avg_stats = (pet.hunger + pet.happiness + pet.cleanliness) / 3

        if pet.willpower < 30 or avg_stats < 25:
            return "Neglected 😥"
        if pet.hunger < 40:
            return "Starving 😫"
        if pet.happiness < 40:
            return "Gloomy 😞"
        if pet.cleanliness < 40:
            return "Grubby 😒"
        if avg_stats < 85:
            return "Content 😐"

        return "Joyful 😊"

    def _care_for_pet(self, user_id: str, stat_name: str, restore_amount: int):
        """Performs a care action on your pet to restore a specific stat."""
        stat_name = stat_name.lower()

        # 1. Fetch the rules for this action from the database
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT * FROM stat_definitions WHERE stat_name = ?", (stat_name,)
            )
            stat_definition = cur.fetchone()

        if not stat_definition:
            return False, f"`{stat_name}` is not a valid target for a care action."

        # 2. Fetch the pet's current data for this stat
        pet = fetch_pet(user_id)
        if not pet or stat_name not in pet._stats:
            return False, str("You don't have a pet to care for!")

        # 3. Perform the cooldown check
        stat_data = pet.get_stat(stat_name)
        cooldown = datetime.timedelta(seconds=stat_definition["cooldown_seconds"] or 0)
        last_cared_str = stat_data["last_updated"]

        if last_cared_str:
            last_cared_time = datetime.datetime.fromisoformat(last_cared_str)
            if datetime.datetime.now() - last_cared_time < cooldown:
                time_remaining = cooldown - (datetime.datetime.now() - last_cared_time)
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                return (
                    False,
                    f"You must wait **{minutes}m {seconds}s** before doing that again.",
                )

        # 4. If cooldown is over, perform the action
        new_value = modify_pet_stat(user_id, stat_name, restore_amount)
        modify_pet_stat(user_id, "willpower", 1)

        return True, new_value

    @tasks.loop(minutes=45)
    async def stat_decay_loop(self):
        with get_db_cursor() as cur:
            # Step 1: Regular stat decay for all pets
            # Get all the rules for stats that are supposed to decay
            cur.execute(
                "SELECT def_id, decay_amount FROM stat_definitions WHERE decay_amount > 0"
            )
            decay_rules = cur.fetchall()

            for rule in decay_rules:
                cur.execute(
                    "UPDATE pet_stats SET stat_value = MAX(0, stat_value - ?) WHERE def_id = ?",
                    (rule["decay_amount"], rule["def_id"]),
                )

            willpower_id = get_stat_definition_id("willpower")

            if not willpower_id:
                print(
                    "Failed to find a valid def_if for the willpower stat. Aborting decay loop..."
                )
                return

            # Step 2: Decrease Willpower for neglected pets (stats at 0)
            cur.execute(
                """
                UPDATE pet_stats
                SET stat_value = MAX(0, stat_value - 5)
                WHERE def_id = ? AND owner_id IN (
                    SELECT owner_id
                    FROM pet_stats
                    WHERE stat_value <= 0
                    AND def_id IN (
                        SELECT def_id FROM stat_definitions WHERE decay_amount > 0 AND decay_amount IS NOT NULL
                    )
                )
            """,
                (willpower_id,),
            )

            # Step 3: Find any pets whose willpower has hit 0
            cur.execute(
                """
                SELECT ps.owner_id, p.name 
                FROM pet_stats ps 
                JOIN pets p ON ps.owner_id = p.user_id 
                WHERE ps.def_id = ? AND ps.stat_value <= 0
            """,
                (willpower_id,),
            )
            pets_to_remove = cur.fetchall()

            for pet in pets_to_remove:
                user_id = pet["user_id"]
                pet_name = pet["name"]

                # Step 4: Delete the pet and its inventory
                cur.execute("DELETE FROM pets WHERE user_id = ?", (user_id,))
                cur.execute("DELETE FROM pet_stats WHERE owner_id = ?", (user_id,))
                cur.execute("DELETE FROM inventory WHERE owner_id = ?", (user_id,))

                # Step 5: Try to send a DM to the user
                try:
                    user = await self.bot.fetch_user(user_id)
                    await user.send(
                        f"You neglected your pet, **{pet_name}**, for too long. It has lost all its Willpower and run away. 😥"
                    )
                except discord.HTTPException:
                    print(
                        f"Failed to send DM to user {user_id}. They might have DMs disabled."
                    )

        print("Database stat decay and neglect loop has run.")

    @stat_decay_loop.before_loop
    async def before_stat_decay_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="hatch")
    async def hatch_pet(self, ctx):
        """Hatches a new pet."""
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (user_id,))
            if cur.fetchone():
                await ctx.send("You already have a pet!")
            else:
                cur.execute(
                    "INSERT INTO pets (user_id, name, born_at) VALUES (?, ?, ?)",
                    (user_id, "Pet", datetime.datetime.now().isoformat()),
                )

                cur.execute("SELECT def_id, default_value FROM stat_definitions")
                default_stats = cur.fetchall()

                for stat in default_stats:
                    cur.execute(
                        "INSERT INTO pet_stats (owner_id, def_id, stat_value) VALUES (?, ?, ?)",
                        (user_id, stat["def_id"], stat["default_value"]),
                    )
                await ctx.send(
                    f"Congratulations, {ctx.author.display_name}! You've hatched a new pet! 🎉"
                )

    @commands.command(name="name")
    async def name_pet(self, ctx, *, new_name: str):
        """Gives your pet a name."""
        user_id = ctx.author.id

        if not (0 < len(new_name) <= 25):
            await ctx.send("The name must be between 1 and 25 characters long.")
            return

        with get_db_cursor() as cur:
            cur.execute(
                "UPDATE pets SET name = ? WHERE user_id = ?", (new_name, user_id)
            )

            if cur.rowcount == 0:
                await ctx.send("You don't have a pet to name! Use `!hatch` first.")
            else:
                await ctx.send(f"You've named your pet **{new_name}**! 🎉")

    @commands.command(name="status")
    async def check_status(self, ctx):
        """Checks your pet's current status."""
        pet = fetch_pet(ctx.author.id)
        if not pet:
            await ctx.send("You don't have a pet yet! Type `!hatch` to get one.")
            return

        age_delta = datetime.datetime.now() - pet.born_at
        hours, remainder = divmod(int(age_delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        mood = self._get_pet_mood(pet)

        embed = discord.Embed(
            title=f"{pet.name}'s Status", color=discord.Color.blue()
        )

        embed.add_field(name="🎭 Mood", value=mood, inline=True)

        for _, stat_data in pet._stats.items():
            display_name = stat_data["display_name"]
            value = stat_data["stat_value"]
            cap = stat_data["cap"]

            display_value = f"{value} / {cap}" if cap is not None else str(value)
            embed.add_field(name=display_name, value=display_value, inline=True)

        embed.add_field(name="🎂 Age", value=f"{hours}h {minutes}m", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="feed")
    async def feed_pet(self, ctx):
        """Feeds your pet to restore hunger."""
        user_id = ctx.author.id
        success, value = self._care_for_pet(user_id, "hunger", 15)

        if not success:
            await ctx.send(value)
            return

        await ctx.send(f"You fed your pet! 🍔 Its hunger is now {value}/100.")

    @commands.command(name="play")
    async def play_with_pet(self, ctx):
        """Plays with your pet to restore happiness and earn coins."""
        user_id = ctx.author.id
        success, value = self._care_for_pet(user_id, "happiness", 20)

        if not success:
            await ctx.send(value)
            return

        money_earned = random.randint(5, 15)
        modify_pet_stat(user_id, "money", money_earned)

        await ctx.send(
            f"You played with your pet! ❤️ Its happiness is now {value}/100. You also earned {money_earned} coins! 💰"
        )

    @commands.command(name="clean")
    async def clean_pet(self, ctx):
        """Cleans your pet to restore cleanliness."""
        user_id = ctx.author.id
        success, value = self._care_for_pet(user_id, "cleanliness", 100)

        if not success:
            await ctx.send(value)
            return

        await ctx.send("You cleaned your pet! ✨ It's sparkling clean now.")

    @commands.command(name="inventory", aliases=["inv"])
    async def show_inventory(self, ctx):
        """Displays the items in your inventory."""
        user_id = ctx.author.id
        with get_db_cursor() as cur:
            cur.execute("SELECT item_id FROM inventory WHERE owner_id = ?", (user_id,))

            items_in_db = cur.fetchall()

            if not items_in_db:
                await ctx.send("Your inventory is empty. Buy items from the `!shop`!")
                return

            item_ids = [item[0] for item in items_in_db]
            item_counts = Counter(item_ids)

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Inventory",
                color=discord.Color.orange(),
            )

            description = ""
            for item_id, count in item_counts.items():
                item_data = fetch_shop_item(item_id)
                if not item_data:
                    await ctx.send(f"Error: Item with ID `{item_id}` not found.")
                    return
                description += f"{item_data['name']} **x{count}**\n"

            embed.description = description
            await ctx.send(embed=embed)

    @commands.command(name="use")
    async def use_item(self, ctx, item_id: str):
        """Uses an item from your inventory."""
        item_id = item_id.lower()
        item = fetch_shop_item(item_id)
        if not item:
            await ctx.send("That item doesn't exist in the shop.")
            return

        user_id = ctx.author.id

        new_stat_value = modify_pet_stat(
            user_id, item["effect_stat"], item["effect_value"]
        )
        modify_pet_stat(user_id, "willpower", 2)

        # Remove item from inventory
        with get_db_cursor() as cur:
            cur.execute("""
                DELETE FROM inventory
                WHERE entry_id = (SELECT entry_id FROM inventory WHERE owner_id = ? AND item_id = ? LIMIT 1)
                """,
                (user_id, item_id),
            )

        await ctx.send(
            f"You used a {item['name']}! Your pet's {item['effect_stat']} is now {new_stat_value}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PetCommands(bot))
