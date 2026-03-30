import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Immediate confirmation that Python is awake
print("--- DEBUG START ---")

# 2. Define the path exactly like your main.py does
_BACKEND_DIR = Path(__file__).resolve().parent
env_path = _BACKEND_DIR / ".env"

print(f"Looking for .env at: {env_path}")
print(f"Does the file exist? {env_path.exists()}")

# 3. Load it
load_dotenv(env_path)

# 4. Check the specific keys
email = os.getenv("DATAFORSEO_EMAIL")
login = os.getenv("DATAFORSEO_LOGIN")
password = os.getenv("DATAFORSEO_PASSWORD")

print(f"DATAFORSEO_EMAIL: {email}")
print(f"DATAFORSEO_LOGIN: {login}")
print(f"DATAFORSEO_PASSWORD: {'[FOUND]' if password else '[NOT FOUND]'}")
print("--- DEBUG END ---")