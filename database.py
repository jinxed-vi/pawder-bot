# database.py
import sqlite3
from contextlib import contextmanager

DB_FILE = "pets.db"

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
                money INTEGER NOT NULL, last_prize TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL, item_id TEXT NOT NULL
            )
        ''')
        cur.execute("PRAGMA table_info(pets)")
        columns = [column[1] for column in cur.fetchall()]
        if 'last_prize' not in columns:
            cur.execute("ALTER TABLE pets ADD COLUMN last_prize TEXT")
            # Add the new willpower column if it doesn't exist
        if 'willpower' not in columns:
            # We add a default value of 100 for existing pets
            cur.execute("ALTER TABLE pets ADD COLUMN willpower INTEGER NOT NULL DEFAULT 100")
        # Add the new 'last_play' column if it doesn't exist
        if 'last_play' not in columns:
            cur.execute("ALTER TABLE pets ADD COLUMN last_play TEXT")
        # Add the new columns for feed and clean cooldowns
        if 'last_feed' not in columns:
            cur.execute("ALTER TABLE pets ADD COLUMN last_feed TEXT")
        if 'last_clean' not in columns:
            cur.execute("ALTER TABLE pets ADD COLUMN last_clean TEXT")


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
