import sqlite3
from pathlib import Path

from reddit_lead_gen.settings import settings

# 1. Clean the 'sqlite:///' prefix from database_url
db_path = settings.database.database_url.replace("sqlite:///", "")

# 2. Resolve relative to project root
project_root = Path(__file__).parent
target_db = (project_root / db_path).resolve()

# 3. Connect and execute
conn = sqlite3.connect(target_db)
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM posts
    WHERE created_utc >= DATETIME('now', '-5 hour');
""")

conn.commit()
print(f"Deleted {cursor.rowcount} entries from the last hour.")
conn.close()
