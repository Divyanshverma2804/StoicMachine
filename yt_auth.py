# """
# yt_auth.py — Run this once on the VM to authorize YouTube access.
# Opens a local auth server on port 8090.

# Usage:
#     python yt_auth.py

# After completing the browser flow, token.json is saved to data/yt_token.json
# and all future uploads happen automatically.
# """
# import os
# from dotenv import load_dotenv
# load_dotenv()

# # Must be run BEFORE the app starts (or with app stopped) so port 8090 is free
# from app.uploader import _get_credentials
# creds = _get_credentials()
# print(f"\n✅ Authorized! Token saved to {os.environ.get('YT_TOKEN_FILE', 'data/yt_token.json')}")
# print("You can now start the app — uploads will happen automatically.")


import os
from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.environ.get("YT_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE = os.environ.get("YT_TOKEN_FILE", "data/yt_token.json")

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)

# Generate the auth URL manually
auth_url, _ = flow.authorization_url(prompt="consent")

print("\n" + "="*60)
print("Open this URL in your browser:")
print("="*60)
print(auth_url)
print("="*60)
code = input("\nPaste the authorization code here: ").strip()

flow.fetch_token(code=code)
creds = flow.credentials

os.makedirs(os.path.dirname(TOKEN_FILE) or ".", exist_ok=True)
with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print(f"\n✅ Authorized! Token saved to {TOKEN_FILE}")