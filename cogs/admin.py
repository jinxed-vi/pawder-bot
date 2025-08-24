# cogs/admin.py
import discord
from discord.ext import commands
from database import get_db_cursor, fetch_shop_item

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='additem')
    @commands.is_owner()
    async def add_item(self, ctx, user: discord.Member, item_id: str, quantity: int = 1):
        """(Admin) Adds an item to a user's inventory."""
        item_id = item_id.lower()
        item_data = fetch_shop_item(item_id)
        if not item_data:
            await ctx.send(f"Error: Item with ID `{item_id}` not found.")
            return
        
        with get_db_cursor() as cur:
            # We add the item 'quantity' times
            for _ in range(quantity):
                cur.execute("INSERT INTO inventory (owner_id, item_id) VALUES (?, ?)", (user.id, item_id))

            await ctx.send(f"✅ Successfully added **{quantity}x {item_data['name']}** to {user.display_name}'s inventory.")

    @commands.command(name='removeitem')
    @commands.is_owner()
    async def remove_item(self, ctx, user: discord.Member, item_id: str, quantity: int = 1):
        """(Admin) Removes an item from a user's inventory."""
        
        item_id = item_id.lower()
        item_data = fetch_shop_item(item_id)
        if not item_data:
            await ctx.send(f"Error: Item with ID `{item_id}` not found.")
            return

        with get_db_cursor() as cur:
            # First, check if the user has enough of the item to remove
            cur.execute("SELECT entry_id FROM inventory WHERE owner_id = ? AND item_id = ?", (user.id, item_id))
            items_in_inventory = cur.fetchall()
            
            if len(items_in_inventory) < quantity:
                await ctx.send(f"Error: {user.display_name} only has {len(items_in_inventory)} of that item, but you tried to remove {quantity}.")
                return

            # Get the specific database entries to delete
            entries_to_delete = [item['entry_id'] for item in items_in_inventory[:quantity]]
            
            # Delete the items by their unique entry_id
            for entry_id in entries_to_delete:
                cur.execute("DELETE FROM inventory WHERE entry_id = ?", (entry_id,))

        await ctx.send(f"✅ Successfully removed **{quantity}x {item_data['name']}** from {user.display_name}'s inventory.")
   
    @commands.command(name='addshopitem')
    @commands.is_owner()
    async def add_shop_item(self, ctx, item_id: str, price: int, effect_stat: str, effect_value: int, name: str, is_visible: int, *, description: str):
        """(Admin) Adds/updates an item. Set visibility with '| visible=false' at the end."""
        item_id = item_id.lower()
        valid_stats = ['hunger', 'happiness', 'cleanliness', 'willpower']
        if effect_stat not in valid_stats:
            await ctx.send(f"Error: `{effect_stat}` is not a valid stat.")
            return

        with get_db_cursor() as cur:
            cur.execute("INSERT OR REPLACE INTO shop VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (item_id, name, price, description, effect_stat, effect_value, is_visible))
        
        visibility_text = "is visible" if is_visible == 1 else "is a hidden prize"
        await ctx.send(f"✅ Shop updated. Item `{item_id}` has been added/modified and {visibility_text}.")

    @commands.command(name='delshopitem')
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
    
    @delete_shop_item.error
    @add_shop_item.error
    async def admin_shop_command_error(self, ctx, error):
        """Error handler for the admin commands."""
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("📋 Please provide all required arguments (`item_id`, `price`, `effect_stat`, `effect_value`, `name`, `is_visible`, `description`).")
        else:
            print(f"An unhandled error occurred in an admin command: {error}")
            await ctx.send("An unexpected error occurred.")

    @add_item.error
    @remove_item.error
    async def admin_command_error(self, ctx, error):
        """Error handler for the admin commands."""
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("📋 Please provide all required arguments (`user`, `item_id`).")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❓ I couldn't find that user. Please mention them or use their ID.")
        else:
            print(f"An unhandled error occurred in an admin command: {error}")
            await ctx.send("An unexpected error occurred.")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))