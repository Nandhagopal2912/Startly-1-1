# this file is to have a peice of codes needed to debug the things using dummy codes and print statements to check the flow of the program and the values of the variables at different stages of the execution. It can be used to identify where the problem is occurring and what might be causing it.


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