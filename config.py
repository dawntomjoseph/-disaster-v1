import os

# SQLite database file location
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'disaster.db')
API_KEY = os.getenv("OPENWEATHER_API_KEY")