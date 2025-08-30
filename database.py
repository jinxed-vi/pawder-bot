# database.py
import datetime
import sqlite3
from contextlib import contextmanager

from utils import Pet

DB_FILE = "pets.db"

INITIAL_SHOP_ITEMS = {
    "apple": {
        "name": "Apple 🍎",
        "price": 10,
        "description": "Restores 25 hunger.",
        "effect_stat": "hunger",
        "effect_value": 25,
    },
    "bread": {
        "name": "Bread 🍞",
        "price": 20,
        "description": "Restores 40 hunger.",
        "effect_stat": "hunger",
        "effect_value": 40,
    },
    "toy": {
        "name": "Squeaky Toy 🧸",
        "price": 30,
        "description": "Restores 35 happiness.",
        "effect_stat": "happiness",
        "effect_value": 35,
    },
    "soap": {
        "name": "Soap Bar 🧼",
        "price": 15,
        "description": "Restores 50 cleanliness.",
        "effect_stat": "cleanliness",
        "effect_value": 50,
    },
}


@contextmanager
def get_db_cursor():
    """A context manager to handle database connection and transactions."""
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        cur = con.cursor()
        yield cur
        con.commit()
    finally:
        con.close()


def setup_database():
    """Sets up the database tables if they don't exist."""
    with get_db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, born_at TEXT NOT NULL,
                last_prize TEXT
            )
        """)


        # TODO Make it so that the stat here is also linked with the stat_definitions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shop (
                item_id TEXT PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL,
                description TEXT NOT NULL, effect_stat TEXT NOT NULL, effect_value INTEGER NOT NULL,
                is_visible INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, item_id TEXT NOT NULL,
                FOREIGN KEY(item_id) REFERENCES shop(item_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS stat_definitions (
                def_id INTEGER PRIMARY KEY,
                stat_name TEXT UNIQUE NOT NULL,
                default_value INTEGER NOT NULL,
                cap INTEGER, -- Can be NULL for stats with no cap, like money
                cooldown_seconds INTEGER, -- Cooldown for the action that restores this stat
                decay_amount INTEGER,
                display_name TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pet_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                def_id INTEGER NOT NULL,
                stat_value INTEGER NOT NULL,
                last_updated TEXT, -- Timestamp of the last time this stat was positively modified
                FOREIGN KEY(def_id) REFERENCES stat_definitions(def_id) ON DELETE CASCADE
            )
        """)

        # One-time population of the definitions table
        cur.execute("SELECT COUNT(*) FROM stat_definitions")
        if cur.fetchone()[0] == 0:
            print("Populating stat definitions for the first time...")

            default_stats = {
                "hunger": {
                    "default": 100,
                    "cap": 100,
                    "cooldown": 1800,  # 30 mins
                    "decay": 2,
                    "display_name": "🍔 Hunger",
                },
                "happiness": {
                    "default": 100,
                    "cap": 100,
                    "cooldown": 300,  # 5 mins
                    "decay": 1,
                    "display_name": "❤️ Happiness",
                },
                "cleanliness": {
                    "default": 100,
                    "cap": 100,
                    "cooldown": 3600,  # 1 hour
                    "decay": 3,
                    "display_name": "✨ Cleanliness",
                },
                "willpower": {
                    "default": 100,
                    "cap": 100,
                    "cooldown": None,
                    "decay": 0,
                    "display_name": "💪 Willpower",
                },
                "money": {
                    "default": 10,
                    "cap": None,
                    "cooldown": None,
                    "decay": 0,
                    "display_name": "💰 Coins",
                },
            }
            for name, p in default_stats.items():
                cur.execute(
                    "INSERT INTO stat_definitions (stat_name, default_value, cap, cooldown_seconds, decay_amount, display_name) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, p["default"], p["cap"], p["cooldown"], p["decay"], p["display_name"]),
                )

        # One-time population of the shop table
        cur.execute("SELECT COUNT(*) FROM shop")
        if cur.fetchone()[0] == 0:
            print("Shop table is empty, populating with initial items...")
            for item_id, details in INITIAL_SHOP_ITEMS.items():
                cur.execute(
                    "INSERT INTO shop VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (
                        item_id,
                        details["name"],
                        details["price"],
                        details["description"],
                        details["effect_stat"],
                        details["effect_value"],
                    ),
                )


def get_stat_definition_id(stat_name):
    """Get a stat's ID from its name."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT def_id FROM stat_definitions WHERE stat_name = ?", (stat_name,)
        )
        result = cur.fetchone()
        return result["def_id"] if result else None


def fetch_pet(user_id) -> Pet | None:
    """Fetches a pet and joins its stats with their stat definitions."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,))
        pet_core = cur.fetchone()
        if not pet_core:
            return None

        pet_data = dict(pet_core)

        cur.execute(
            """
            SELECT sd.stat_name, ps.stat_value, sd.cap, ps.last_updated, sd.cooldown_seconds, sd.display_name
            FROM pet_stats ps
            JOIN stat_definitions sd ON ps.def_id = sd.def_id
            WHERE ps.owner_id = ?
        """,
            (user_id,),
        )

        stats = cur.fetchall()
        pet_data["stats"] = {stat["stat_name"]: dict(stat) for stat in stats}

        return Pet(pet_data)


def modify_pet_stat(user_id, stat_name, amount, mode="add"):
    """
    Modifies a pet's stat securely.
    - user_id: The ID of the user whose pet to modify.
    - stat_name: The name of the column/stat to change.
    - amount: The number to add or set.
    - mode: 'add' (default) or 'set'.
    Returns the new value of the stat, or None if the pet doesn't exist.
    """
    def_id = get_stat_definition_id(stat_name)
    if not def_id:
        return None

    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT ps.stat_value, sd.cap
            FROM pet_stats ps
            JOIN stat_definitions sd ON ps.def_id = sd.def_id
            WHERE ps.owner_id = ? AND ps.def_id = ?
        """,
            (user_id, def_id),
        )
        current = cur.fetchone()
        if not current:
            return None

        new_value = 0
        cap = current["cap"]

        if mode == "add":
            new_value = current["stat_value"] + amount
            # If there is a cap, apply it. Otherwise, let the value be whatever it is.
            if cap is not None:
                new_value = max(0, min(cap, new_value))
        elif mode == "set":
            new_value = amount
            if cap is not None:
                new_value = max(0, min(cap, new_value))

        cur.execute(
            "UPDATE pet_stats SET stat_value = ?, last_updated = ? WHERE owner_id = ? AND def_id = ?",
            (new_value, datetime.datetime.now().isoformat(), user_id, def_id),
        )
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
