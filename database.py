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