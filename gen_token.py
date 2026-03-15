# gen_token.py
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE    = os.environ.get("YT_TOKEN_FILE",    "data/yt_token.json")

os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
flow  = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
creds = flow.run_local_server(port=8090)

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print(f"\n✅ Token saved to: {TOKEN_FILE}")
print(f"   Scopes: {creds.scopes}")
