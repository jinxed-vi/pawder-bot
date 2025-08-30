from typing import Optional
import discord
from discord.ext import commands
import datetime
import random
from database import (
    get_db_cursor,
    fetch_pet,
    modify_pet_stat,
    fetch_all_shop_items,
    fetch_shop_item,
)


class EconomyCommands(commands.Cog, name="📈 Economy Commands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="shop")
    async def show_shop(self, ctx: commands.Context):
        """Displays the items available for purchase in the shop."""
        # The query now filters for is_visible = 1
        shop_items = fetch_all_shop_items()

        embed = discord.Embed(
            title="Pet Shop",
            description="Use `!buy <item_id>` to purchase an item.",
            color=discord.Color.gold(),
        )

        visible_items_found = False
        for item in shop_items:
            if item["is_visible"] == 1:
                embed.add_field(
                    name=f"{item['name']} - {item['price']} Coins",
                    value=f"`{item['item_id']}` - {item['description']}",
                    inline=False,
                )
                visible_items_found = True

        if not visible_items_found:
            embed.description = "The shop is currently empty!"

        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy_item(self, ctx, item_id: str):
        """Buys an item from the shop and adds it to your inventory."""

        item_id = item_id.lower()
        item = fetch_shop_item(item_id)
        if not item:
            await ctx.send("That item doesn't exist in the shop.")
            return

        user_id = ctx.author.id

        pet = fetch_pet(user_id)
        if not pet:
            await ctx.send("You need to hatch a pet first!")
            return
        if pet.money < item["price"]:
            await ctx.send(
                f"You don't have enough money! You need {item['price']} coins but only have {pet.money}."
            )
            return

        modify_pet_stat(user_id, "money", -item["price"])
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)",
                (user_id, item_id),
            )

        await ctx.send(f"You bought a {item['name']}! It's in your inventory.")

    @commands.command(name="prize")
    async def claim_prize(self, ctx: commands.Context):
        """Claims a daily prize of a random item."""
        user_id = ctx.author.id
        cooldown = datetime.timedelta(hours=24)

        pet = fetch_pet(user_id)

        if not pet:
            await ctx.send("You need to `!hatch` a pet before claiming a prize.")
            return

        time_since_claim = datetime.datetime.now() - pet.last_prize

        if time_since_claim < cooldown:
            time_remaining = cooldown - time_since_claim
            hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.send(
                f"You've already claimed your prize. Please wait **{hours}h {minutes}m**."
            )
            return

        with get_db_cursor() as cur:
            # If cooldown is over, grant a random item prize
            cur.execute("SELECT item_id FROM shop")
            all_possible_items = cur.fetchall()

            if not all_possible_items:
                await ctx.send(
                    "There are no items available to win as prizes right now!"
                )
                return

            won_item_id = random.choice(all_possible_items)["item_id"]
            item_details = fetch_shop_item(won_item_id)

            # Add item to inventory and update timestamp
            cur.execute(
                "INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)",
                (ctx.author.id, won_item_id),
            )
            cur.execute(
                "UPDATE pets SET last_prize = ? WHERE user_id = ?",
                (datetime.datetime.now().isoformat(), ctx.author.id),
            )

        await ctx.send(
            f"You claimed your daily prize and received a {item_details['name']}! It's now in your inventory."
        )

    @commands.command(name="leaderboard", aliases=["lb"])
    async def show_leaderboard(self, ctx: commands.Context):
        """Shows the top 10 richest pet owners."""

        with get_db_cursor() as cur:
            # The SQL query to get the top 10 users, sorted by money
            cur.execute("""
                SELECT ps.owner_id
                FROM pet_stats ps
                JOIN stat_definitions sd ON ps.def_id = sd.def_id
                WHERE sd.stat_name = 'money'
                ORDER BY ps.stat_value DESC LIMIT 10
            """)
            top_users = cur.fetchall()

        if not top_users:
            await ctx.send("There's no one on the leaderboard yet!")
            return

        embed = discord.Embed(
            title="💰 Top 10 Richest Pets", color=discord.Color.green()
        )

        description = ""
        for rank, user_data in enumerate(top_users, start=1):
            # We need to fetch the Discord user object to get their current name
            # This is an API call, so it can be slow if the leaderboard is long
            userId = user_data["owner_id"]
            user = self.bot.get_user(userId)
            if user:
                user_display_name = user.display_name
            else:
                user_display_name = "Unknown User"  # If the user has left the server

            pet = fetch_pet(userId)
            if not pet:
                print(f"Could not find pet from owner {user_data['owner_id']}")
                continue

            description += (
                f"**{rank}.** {user_display_name}'s *{pet.name}* - {pet.money} Coins\n"
            )

        embed.description = description
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCommands(bot))
