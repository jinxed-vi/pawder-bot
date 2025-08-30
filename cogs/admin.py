from typing import Optional
import discord
from discord.ext import commands
from database import get_db_cursor, fetch_shop_item, get_stat_definition_id


class AdminCommands(commands.Cog, name="👮‍♀️ Admin Commands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="additem")
    @commands.is_owner()
    async def add_item(
        self, ctx, user: discord.Member, item_id: str, quantity: int = 1
    ):
        """(Admin) Adds an item to a user's inventory."""
        item_id = item_id.lower()
        item_data = fetch_shop_item(item_id)
        if not item_data:
            await ctx.send(f"Error: Item with ID `{item_id}` not found.")
            return

        with get_db_cursor() as cur:
            # We add the item 'quantity' times
            for _ in range(quantity):
                cur.execute(
                    "INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)",
                    (user.id, item_id),
                )

            await ctx.send(
                f"✅ Successfully added **{quantity}x {item_data['name']}** to {user.display_name}'s inventory."
            )

    @commands.command(name="removeitem")
    @commands.is_owner()
    async def remove_item(
        self, ctx, user: discord.Member, item_id: str, quantity: int = 1
    ):
        """(Admin) Removes an item from a user's inventory."""

        item_id = item_id.lower()
        item_data = fetch_shop_item(item_id)
        if not item_data:
            await ctx.send(f"Error: Item with ID `{item_id}` not found.")
            return

        with get_db_cursor() as cur:
            # First, check if the user has enough of the item to remove
            cur.execute(
                "SELECT entry_id FROM inventory WHERE owner_id = ? AND item_id = ?",
                (user.id, item_id),
            )
            items_in_inventory = cur.fetchall()

            if len(items_in_inventory) < quantity:
                await ctx.send(
                    f"Error: {user.display_name} only has {len(items_in_inventory)} of that item, but you tried to remove {quantity}."
                )
                return

            # Get the specific database entries to delete
            entries_to_delete = [
                item["entry_id"] for item in items_in_inventory[:quantity]
            ]

            # Delete the items by their unique entry_id
            for entry_id in entries_to_delete:
                cur.execute("DELETE FROM inventory WHERE entry_id = ?", (entry_id,))

        await ctx.send(
            f"✅ Successfully removed **{quantity}x {item_data['name']}** from {user.display_name}'s inventory."
        )

    @commands.command(name="addshopitem")
    @commands.is_owner()
    async def add_shop_item(
        self,
        ctx,
        item_id: str,
        price: int,
        effect_stat: str,
        effect_value: int,
        name: str,
        is_visible: int,
        description: str,
    ):
        """(Admin) Adds/updates an item.

        **Example**:
        ```
        !addshopitem PowPowTreat 5 happiness 10 "Pow's Perfect Treats 🍬" 1 "Powder loves these things! a wonderful snack that makes any pup's tail wag"
        ```
        """
        item_id = item_id.lower()
        
        def_id = get_stat_definition_id(effect_stat)
        if not def_id:
            await ctx.send(f"Error: `{effect_stat}` is not a valid stat.")
            return
        
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO shop VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    name,
                    price,
                    description,
                    effect_stat,
                    effect_value,
                    is_visible,
                ),
            )

        visibility_text = "is visible" if is_visible == 1 else "is a hidden prize"
        await ctx.send(
            f"✅ Shop updated. Item `{item_id}` has been added/modified and {visibility_text}."
        )

    @commands.command(name="delshopitem")
    @commands.is_owner()
    async def delete_shop_item(self, ctx, item_id: str):
        """(Admin) Deletes an item from the shop."""
        item_id = item_id.lower()
        with get_db_cursor() as cur:
            cur.execute("DELETE FROM shop WHERE item_id = ?", (item_id,))
            if cur.rowcount == 0:
                await ctx.send(f"Error: Item `{item_id}` not found in the shop.")
            else:
                await ctx.send(f"✅ Item `{item_id}` has been removed from the shop.")

    @commands.command(name="addstat")
    @commands.is_owner()
    async def add_stat(
        self,
        ctx,
        stat_name: str,
        default: int,
        display_name: str,
        decay: int = 0,
        cap: Optional[int] = None,
        cooldown: Optional[int] = None,
    ):
        """(Admin) Adds/updates a stat's definition. Cooldown is in seconds."""
        stat_name = stat_name.lower()
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO stat_definitions (stat_name, default_value, cap, cooldown_seconds, decay_amount, display_name) VALUES (?, ?, ?, ?, ?, ?)",
                (stat_name, default, cap, cooldown, decay, display_name),
            )
            # Get the ID of the stat we just created/updated
            new_stat_id = cur.lastrowid

            cur.execute("SELECT user_id FROM pets")
            all_users = cur.fetchall()
            added_count = 0
            for user in all_users:
                cur.execute(
                    "SELECT 1 FROM pet_stats WHERE owner_id = ? AND def_id = ?",
                    (user["user_id"], new_stat_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO pet_stats (owner_id, def_id, stat_value) VALUES (?, ?, ?)",
                        (user["user_id"], new_stat_id, default),
                    )
                    added_count += 1

        await ctx.send(
            f"✅ Stat definition for `{stat_name}` has been set. Added to **{added_count}** existing pets."
        )
    
    @commands.command(name='delstat')
    @commands.is_owner()
    async def delete_stat(self, ctx, stat_name: str):
        """(Admin) Deletes a stat definition and all instances of it from pets."""
        stat_name = stat_name.lower()
        with get_db_cursor() as cur:
            cur.execute("DELETE FROM stat_definitions WHERE stat_name = ?", (stat_name,))
            cur.execute("DELETE FROM shop WHERE effect_stat = ?", (stat_name,))
            if cur.rowcount == 0:
                await ctx.send(f"Error: The stat `{stat_name}` was not found.")
            else:
                await ctx.send(f"✅ Deleted the stat `{stat_name}`. All pet instances of this stat have been automatically removed.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))
