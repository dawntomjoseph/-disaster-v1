import sqlite3
from config import DATABASE_PATH


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS taluk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        district TEXT,
        population INTEGER,
        username TEXT,
        password TEXT,
        elevation REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taluk_id INTEGER,
        boats INTEGER,
        rescue_vehicles INTEGER,
        relief_camps INTEGER,
        FOREIGN KEY (taluk_id) REFERENCES taluk(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS monitoring (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taluk_name TEXT,
        volunteer_name TEXT,
        assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
        completion_status TEXT DEFAULT 'Active',
        assignment_location TEXT,
        mon_availability TEXT,
        FOREIGN KEY (taluk_name) REFERENCES taluk(name),
        FOREIGN KEY (volunteer_name) REFERENCES volunteers(name),
        FOREIGN KEY (mon_availability) REFERENCES volunteers(availability)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        username TEXT,
        password TEXT,
        taluk_id INTEGER,
        availability TEXT,
        FOREIGN KEY (taluk_id) REFERENCES taluk(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rainfall_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taluk_id INTEGER,
        date TEXT,
        rainfall_mm REAL,
        FOREIGN KEY (taluk_id) REFERENCES taluk(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resource_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taluk_id INTEGER,
    resource_type TEXT,
    quantity INTEGER, 
    status TEXT DEFAULT 'PENDING',
    FOREIGN KEY (taluk_id) REFERENCES taluk(id)
)
""")
    # Taluk officer contact information (one per taluk)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS taluk_contact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taluk_id INTEGER UNIQUE,
        officer_name TEXT,
        phone TEXT,
        email TEXT,
        FOREIGN KEY (taluk_id) REFERENCES taluk(id)
    )
    """)

    # Backfill missing columns when DB already existed
    def ensure_column(table, column, col_type):
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    ensure_column('taluk', 'username', 'TEXT')
    ensure_column('taluk', 'password', 'TEXT')
    ensure_column('volunteers', 'username', 'TEXT')
    ensure_column('volunteers', 'password', 'TEXT')
    ensure_column('monitoring', 'assigned_date', 'TEXT')
    ensure_column('monitoring', 'completion_status', 'TEXT')
    ensure_column('monitoring', 'assignment_location', 'TEXT')
    ensure_column('resource_requests', 'reason', 'TEXT')

    # Ensure all taluks have resources entries
    cur.execute("""
    INSERT OR IGNORE INTO resources (taluk_id, boats, rescue_vehicles, relief_camps)
    SELECT id, 0, 0, 0 FROM taluk
    """)

    db.commit()
    db.close()
