import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
print("BASE_DIR:", BASE_DIR)
print("Before load:", os.environ.get("DATABASE_URL"))
load_dotenv(BASE_DIR / ".env")
print("After load:", os.environ.get("DATABASE_URL"))

db_url = os.environ.get("DATABASE_URL")
if db_url:
    import dj_database_url
    print("Parsed:", dj_database_url.parse(db_url))
else:
    print("DATABASE_URL is empty, skipping parse.")
