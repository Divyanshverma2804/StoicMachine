"""
uploader.py — YouTube Data API v3 upload via OAuth2 service-account token
or installed-app flow (token stored in token.json).
"""
import os, logging, json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

log = logging.getLogger("uploader")

SCOPES            = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE= os.environ.get("YT_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE        = os.environ.get("YT_TOKEN_FILE",     "data/yt_token.json")

YT_CATEGORY_ID    = os.environ.get("YT_CATEGORY_ID", "22")   # 22 = People & Blogs
YT_PRIVACY        = os.environ.get("YT_PRIVACY",     "public")  # public/unlisted/private
YT_TAGS           = os.environ.get("YT_TAGS",        "motivation,mindset,philosophy").split(",")


def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8090)
        os.makedirs(os.path.dirname(TOKEN_FILE) or ".", exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def upload_video(video_path: str, title: str, description: str = "") -> str:
    """
    Uploads video_path to YouTube.
    Returns the YouTube video ID.
    """
    log.info(f"[upload] Starting upload: {title}")
    creds   = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":       title,
            "description": description or title,
            "tags":        YT_TAGS,
            "categoryId":  YT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": YT_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info(f"[upload] Progress: {int(status.progress()*100)}%")

    video_id = response["id"]
    log.info(f"[upload] Done: https://youtu.be/{video_id}")
    return video_id
