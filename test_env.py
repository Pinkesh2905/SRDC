import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
print("BASE_DIR:", BASE_DIR)
print("Before load:", os.environ.get("DATABASE_URL"))
load_dotenv(BASE_DIR / ".env")
print("After load:", os.environ.get("DATABASE_URL"))

import dj_database_url
print("Parsed:", dj_database_url.parse(os.environ.get("DATABASE_URL") or ""))
