"""
yt_auth.py — Run this once on the VM to authorize YouTube access.
Opens a local auth server on port 8090.

Usage:
    python yt_auth.py

After completing the browser flow, token.json is saved to data/yt_token.json
and all future uploads happen automatically.
"""
import os
from dotenv import load_dotenv
load_dotenv()

# Must be run BEFORE the app starts (or with app stopped) so port 8090 is free
from app.uploader import _get_credentials
creds = _get_credentials()
print(f"\n✅ Authorized! Token saved to {os.environ.get('YT_TOKEN_FILE', 'data/yt_token.json')}")
print("You can now start the app — uploads will happen automatically.")
