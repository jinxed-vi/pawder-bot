# database.py
import sqlite3
from contextlib import contextmanager

DB_FILE = "pets.db"

INITIAL_SHOP_ITEMS = {
    "apple": {"name": "Apple 🍎", "price": 10, "description": "Restores 25 hunger.", "effect_stat": "hunger", "effect_value": 25},
    "bread": {"name": "Bread 🍞", "price": 20, "description": "Restores 40 hunger.", "effect_stat": "hunger", "effect_value": 40},
    "toy": {"name": "Squeaky Toy 🧸", "price": 30, "description": "Restores 35 happiness.", "effect_stat": "happiness", "effect_value": 35},
    "soap": {"name": "Soap Bar 🧼", "price": 15, "description": "Restores 50 cleanliness.", "effect_stat": "cleanliness", "effect_value": 50}
}

@contextmanager
def get_db_cursor():
    """A context manager to handle database connection and transactions."""
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        yield cur
        con.commit()
    finally:
        con.close()

def setup_database():
    """Sets up the database tables if they don't exist."""
    with get_db_cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS pets (
                user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, born_at TEXT NOT NULL,
                hunger INTEGER NOT NULL, happiness INTEGER NOT NULL, cleanliness INTEGER NOT NULL,
                money INTEGER NOT NULL, last_prize TEXT, willpower INTEGER NOT NULL DEFAULT 100,
                last_play TEXT, last_feed TEXT, last_clean TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, item_id TEXT NOT NULL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS shop (
                item_id TEXT PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL,
                description TEXT NOT NULL, effect_stat TEXT NOT NULL, effect_value INTEGER NOT NULL,
                is_visible INTEGER NOT NULL DEFAULT 1
            )
        ''')
        
        # One-time migration: Check if the shop table is empty
        cur.execute("SELECT COUNT(*) FROM shop")
        if cur.fetchone()[0] == 0:
            print("Shop table is empty, populating with initial items...")
            for item_id, details in INITIAL_SHOP_ITEMS.items():
                cur.execute("INSERT INTO shop VALUES (?, ?, ?, ?, ?, ?, 1)",
                            (item_id, details['name'], details['price'], details['description'], 
                             details['effect_stat'], details['effect_value']))
        
def fetch_pet(user_id):
    """Fetches a single pet's data from the database."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,))
        return cur.fetchone()

def modify_pet_stat(user_id, stat_name, amount, mode='add'):
    """
    Modifies a pet's stat securely.
    - user_id: The ID of the user whose pet to modify.
    - stat_name: The name of the column/stat to change.
    - amount: The number to add or set.
    - mode: 'add' (default) or 'set'.
    Returns the new value of the stat, or None if the pet doesn't exist.
    """
    # Whitelist of valid stats to prevent SQL injection
    valid_stats = ['hunger', 'happiness', 'cleanliness', 'money', 'willpower']
    if stat_name not in valid_stats:
        raise ValueError(f"Invalid stat name: {stat_name}")

    with get_db_cursor() as cur:
        # First, check if the pet exists
        cur.execute("SELECT 1 FROM pets WHERE user_id = ?", (user_id,))
        if not cur.fetchone():
            return None

        if mode == 'add':
            # Cap stats between 0 and 100, but not money
            if stat_name != 'money':
                query = f"UPDATE pets SET {stat_name} = MIN(100, MAX(0, {stat_name} + ?)) WHERE user_id = ?"
            else: # Money has no upper cap
                query = "UPDATE pets SET money = money + ? WHERE user_id = ?"
            cur.execute(query, (amount, user_id))
        
        elif mode == 'set':
            query = f"UPDATE pets SET {stat_name} = ? WHERE user_id = ?"
            cur.execute(query, (amount, user_id))
        
        # Return the new value of the stat
        cur.execute(f"SELECT {stat_name} FROM pets WHERE user_id = ?", (user_id,))
        new_value = cur.fetchone()[stat_name]
        return new_value

def fetch_all_shop_items():
    """Fetches all items from the shop table."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM shop ORDER BY price ASC")
        return cur.fetchall()

def fetch_shop_item(item_id: str):
    """Fetches a single item from the shop table."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM shop WHERE item_id = ?", (item_id,))
        return cur.fetchone()