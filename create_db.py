import sqlite3
from datetime import datetime

# Create or connect to the database
conn = sqlite3.connect('disaster_relief.db')
cursor = conn.cursor()

# Create Volunteer table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS volunteer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        skills TEXT,
        availability TEXT,
        bio TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Create Taluk table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS taluk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        name TEXT NOT NULL UNIQUE,
        population INTEGER NOT NULL,
        elevation REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Commit the changes
conn.commit()
print("Database and tables created successfully!")

# Display table info
cursor.execute("PRAGMA table_info(volunteer)")
print("\nVolunteer table schema:")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[2]}")

cursor.execute("PRAGMA table_info(taluk)")
print("\nTaluk table schema:")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[2]}")

conn.close()
