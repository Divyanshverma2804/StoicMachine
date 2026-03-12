"""
uploader.py — YouTube Data API v3 upload via OAuth2 service-account token
or installed-app flow (token stored in token.json).

Tag strategy for YouTube Shorts
────────────────────────────────
• YT Shorts has no separate "Tags" field visible to viewers.
• Tags should appear as #Hashtags in the title (100-char cap) and description.
• Tags are extracted per-reel from the reel script using keyword analysis so
  each reel gets contextually relevant tags rather than one global set.
"""
import os, re, logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

log = logging.getLogger("uploader")

SCOPES             = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.environ.get("YT_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE         = os.environ.get("YT_TOKEN_FILE",     "data/yt_token.json")

YT_CATEGORY_ID     = os.environ.get("YT_CATEGORY_ID", "22")   # 22 = People & Blogs
YT_PRIVACY         = os.environ.get("YT_PRIVACY",     "public")
YT_TITLE_LIMIT     = 100   # YouTube hard limit

# ─── Fallback global tags if script yields nothing ────────────────────────────
_FALLBACK_TAGS = [
    "motivation", "mindset", "philosophy", "stoicism", "shorts",
    "selfimprovement", "discipline", "wisdom",
]

# ─── Keyword → tag mapping (order matters: first match wins priority) ─────────
_KEYWORD_TAGS: list[tuple[str, str]] = [
    # stoic / philosophy
    (r"stoic|stoicism|marcus|aurelius|epictetus|seneca",  "stoicism"),
    (r"philosophy|philosophical",                          "philosophy"),
    (r"wisdom|wise",                                       "wisdom"),
    # discipline / habits
    (r"disciplin",                                         "discipline"),
    (r"habit|routine",                                     "habits"),
    (r"consistency|consistent",                            "consistency"),
    (r"focus|concentrate",                                 "focus"),
    # mindset / mental
    (r"mindset|mentality",                                 "mindset"),
    (r"mental.strength|resilience|resilient",              "resilience"),
    (r"confident|confidence|belief",                       "confidence"),
    (r"anxiety|fear|worry",                                "anxiety"),
    (r"emotion|feeling",                                   "emotionalintelligence"),
    # success / growth
    (r"success|successful",                                "success"),
    (r"growth|grow|level.?up",                              "personalgrowth"),
    (r"self.?improv",                                       "selfimprovement"),
    (r"goal|purpose|ambition",                             "goals"),
    (r"productiv",                                         "productivity"),
    (r"motivation|motivated",                              "motivation"),
    # life lessons
    (r"lesson|learn|knowledge",                            "lifelessons"),
    (r"hard.?work|effort|grind",                           "hardwork"),
    (r"patience|patient",                                  "patience"),
    (r"gratitude|grateful|thankful",                       "gratitude"),
    (r"happiness|happy|joy",                               "happiness"),
    (r"solitude|alone|loneliness",                         "solitude"),
    (r"wealth|money|rich",                                 "wealth"),
    (r"health|fit|exercise|body",                          "health"),
    (r"sleep|rest|recover",                                "sleep"),
    (r"relation|love|friend",                              "relationships"),
    (r"leader|leadership",                                 "leadership"),
    (r"courage|brave|bold",                                "courage"),
    # always append Shorts tags
    (r".",                                                 "shorts"),
    (r".",                                                 "youtubeshorts"),
]


def extract_tags_from_script(script: str, max_tags: int = 10) -> list[str]:
    """
    Analyse the reel script text and return an ordered list of contextually
    relevant hashtag strings (without the # prefix).
    """
    text  = script.lower()
    seen  = set()
    tags  = []
    for pattern, tag in _KEYWORD_TAGS:
        if tag in seen:
            continue
        if re.search(pattern, text):
            seen.add(tag)
            tags.append(tag)
        if len(tags) >= max_tags:
            break
    # If we only got the mandatory shorts tags, pad with fallbacks
    if len(tags) < 4:
        for fb in _FALLBACK_TAGS:
            if fb not in seen:
                tags.append(fb)
                seen.add(fb)
            if len(tags) >= max_tags:
                break
    return tags


def build_yt_title_and_description(
    reel_name: str,
    script: str,
    extra_description: str = "",
) -> tuple[str, str]:
    """
    Build a YouTube Shorts-optimised title (≤100 chars) and description.

    Strategy
    ─────────
    title = "<Human Reel Name> #tag1 #tag2 …"   (truncated to 100 chars)
    Any tags that don't fit in the title are placed at the top of description.
    """
    tags        = extract_tags_from_script(script)
    base_title  = reel_name.replace("_", " ").strip().title()
    title_limit = YT_TITLE_LIMIT

    # Build title greedily
    title_tags: list[str] = []
    desc_tags:  list[str] = []
    current     = base_title

    for tag in tags:
        candidate = f"{current} #{tag}"
        if len(candidate) <= title_limit:
            current = candidate
            title_tags.append(tag)
        else:
            desc_tags.append(tag)

    title = current

    # Build description
    desc_parts = []
    if desc_tags:
        desc_parts.append(" ".join(f"#{t}" for t in desc_tags))
    if extra_description:
        desc_parts.append(extra_description)
    # Always include all hashtags also in description for discoverability
    all_hash = " ".join(f"#{t}" for t in tags)
    desc_parts.append(all_hash)

    description = "\n\n".join(desc_parts)
    log.info(
        f"[uploader] title ({len(title)} chars): {title!r}  "
        f"| title_tags={title_tags}  desc_tags={desc_tags}"
    )
    return title, description


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


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
) -> str:
    """
    Uploads video_path to YouTube.  Returns the YouTube video ID.
    `title` and `description` should already be pre-built by
    build_yt_title_and_description(); `tags` is the raw tag list for the
    API snippet (separate from hashtags embedded in title/description).
    """
    log.info(f"[upload] Starting upload: {title!r}")
    creds   = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":       title[:YT_TITLE_LIMIT],
            "description": description or title,
            "tags":        tags or _FALLBACK_TAGS,
            "categoryId":  YT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": YT_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info(f"[upload] Progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    log.info(f"[upload] Done: https://youtu.be/{video_id}")
    return video_id
