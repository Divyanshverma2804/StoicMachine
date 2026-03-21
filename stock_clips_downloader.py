"""
stock_clips_downloader.py
Bulk downloads video clips from Pexels API.

Features:
  - Auto-retry on timeout (3 attempts per request)
  - Resume support — skips already downloaded files
  - Progress saved to progress.json — safe to interrupt and restart
  - Longer timeouts for large video files
  - Rate limit aware — backs off on 429 responses
"""

import os
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# load .env variables
load_dotenv()

# ── CONFIG ────────────────────────────────────────────────

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OUTPUT_DIR     = "stock/clips"
PROGRESS_FILE  = "stock_download_progress.json"

CLIPS_PER_SEARCH = 5
MIN_DURATION     = 8    # seconds
MAX_DURATION     = 30   # seconds

API_TIMEOUT      = 20   # seconds for API calls
DL_TIMEOUT       = 90   # seconds for video file downloads (larger files)
RETRY_ATTEMPTS   = 3
RETRY_BACKOFF    = 2    # seconds between retries

# ── SEARCH TERMS ──────────────────────────────────────────
SEARCHES = {
    # ── New relatable channel ──────────────────────────────
    "loneliness": [
        "person alone city night",
        "metro platform empty",
        "rain window alone",
        "walking alone crowd",
        "empty cafe night",
        "sitting alone bench",
        "rainy street night",
    ],
    "overthinking": [
        "person phone dark room",
        "lying bed night",
        "thinking alone dark",
        "scrolling phone night",
        "staring window night",
        "dark room light phone",
    ],
    "pressure": [
        "typing laptop night",
        "city rush hour",
        "desk lamp working late",
        "busy street urban",
        "deadline stress work",
        "city commute morning",
    ],
    "nostalgia": [
        "sunset street empty",
        "golden hour quiet street",
        "childhood playground sunset",
        "old neighbourhood walk",
        "autumn leaves slow motion",
        "vintage film street",
    ],
    "relationships": [
        "empty chair cafe",
        "two cups coffee table",
        "rain window reflection",
        "walking apart silhouette",
        "empty park bench",
        "couple distance street",
    ],
    "clarity": [
        "night drive car window",
        "open road night",
        "dawn window light",
        "sunrise rooftop city",
        "walking sunrise city",
        "road trip window view",
    ],
    "family": [
        "hands elder person",
        "kitchen morning light",
        "doorway home light",
        "family candid indoor",
        "parent child hands",
    ],
    "friendship": [
        "friends walking street",
        "empty park bench",
        "group friends candid",
        "coffee friends table",
        "laughing friends outdoor",
    ],
    # ── Silenor stoic channel ──────────────────────────────
    "silent_power": [
        "storm clouds dramatic sky",
        "lone figure mountain",
        "dark ocean waves night",
        "dramatic lightning",
        "silhouette sunset mountain",
        "fog forest dark",
    ],
    "discipline": [
        "gym training dark",
        "running night city",
        "early morning workout",
        "boxing training",
        "athlete training dark",
        "running sunrise",
    ],
    "stoic_philosophy": [
        "ancient ruins sunset",
        "old library candle",
        "stone architecture dramatic",
        "meditation alone nature",
        "contemplative landscape",
    ],
    "harsh_truths": [
        "dramatic storm sky",
        "dark city rain",
        "empty road dramatic sky",
        "lightning dark clouds",
        "waves crashing rocks",
    ],
    # ── Style variety ──────────────────────────────────────
    "abstract": [
        "bokeh light blur night",
        "light leak cinematic",
        "particle effect dark",
        "neon reflection rain",
        "smoke dark background",
        "water surface reflection",
    ],
    "retro": [
        "film grain vintage street",
        "super8 style footage",
        "vintage car driving",
        "old film aesthetic",
        "retro city street",
    ],
    "nature_minimal": [
        "rain falling slow motion",
        "fog morning forest",
        "water drops window",
        "snow falling slow",
        "steam coffee close up",
        "candle flame dark",
    ],
}


# ── HTTP SESSION with retry ───────────────────────────────

def make_session() -> requests.Session:
    """Create a requests session with automatic retry on connection errors."""
    session = requests.Session()
    retry = Retry(
        total=RETRY_ATTEMPTS,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = make_session()


# ── PROGRESS TRACKING ─────────────────────────────────────

def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def mark_done(progress: dict, category: str, query: str):
    if category not in progress:
        progress[category] = []
    if query not in progress[category]:
        progress[category].append(query)
    save_progress(progress)


def is_done(progress: dict, category: str, query: str) -> bool:
    return query in progress.get(category, [])


# ── DOWNLOAD ──────────────────────────────────────────────

def download_clip(url: str, filepath: str) -> bool:
    """Download a video file with retry on timeout. Returns True on success."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            r = SESSION.get(url, stream=True, timeout=DL_TIMEOUT)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=16384):
                    f.write(chunk)
            return True
        except requests.exceptions.Timeout:
            print(f"    ⏱ Timeout on attempt {attempt}/{RETRY_ATTEMPTS}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF * attempt)
        except requests.exceptions.RequestException as e:
            print(f"    ✗ Download error: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF)
        except KeyboardInterrupt:
            # Clean up partial file
            if os.path.exists(filepath):
                os.remove(filepath)
            raise
    return False


def fetch_and_download(
    category: str,
    query: str,
    folder: str,
    existing_count: int,
) -> int:
    """
    Search Pexels for clips matching query and download them.
    Returns updated clip count for the category.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    params  = {
        "query":       query,
        "per_page":    CLIPS_PER_SEARCH,
        "orientation": "portrait",
        "size":        "medium",
    }

    # API call with retry
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = SESSION.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=API_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"    ⚠ Rate limited — waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.exceptions.Timeout:
            print(f"    ⏱ API timeout attempt {attempt}/{RETRY_ATTEMPTS}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF * attempt)
            else:
                print(f"    ✗ Giving up on query: {query}")
                return existing_count
        except requests.exceptions.RequestException as e:
            print(f"    ✗ API error: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF)
            else:
                return existing_count

    videos    = data.get("videos", [])
    count     = existing_count
    os.makedirs(folder, exist_ok=True)

    for video in videos:
        dur = video.get("duration", 0)
        if dur < MIN_DURATION or dur > MAX_DURATION:
            continue

        # Pick best portrait file
        files = video.get("video_files", [])
        portrait = [f for f in files if f.get("width", 1) < f.get("height", 0)]
        pool     = portrait if portrait else files
        pool.sort(key=lambda f: f.get("width", 0) * f.get("height", 0), reverse=True)

        if not pool:
            continue

        url   = pool[0].get("link", "")
        count += 1
        fname = (
            f"{category}_{query.replace(' ', '_')[:20]}_{count}.mp4"
        )
        fpath = os.path.join(folder, fname)

        if os.path.exists(fpath):
            print(f"    ⏭ Already exists: {fname}")
            continue

        print(f"    ↓ {fname} ({dur}s)", end="", flush=True)
        ok = download_clip(url, fpath)
        if ok:
            print(" ✓")
        else:
            print(" ✗ Failed — skipping")
            count -= 1   # don't count failed downloads

        time.sleep(0.5)   # gentle rate limiting

    return count


# ── MAIN ──────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    progress = load_progress()

    print(f"\n{'='*52}")
    print(f"  Stock Clip Downloader — Pexels API")
    print(f"  Output: {OUTPUT_DIR}/")
    print(f"  Progress file: {PROGRESS_FILE}")
    print(f"  Safe to interrupt — will resume from where it left off")
    print(f"{'='*52}\n")

    total_all = 0

    for category, queries in SEARCHES.items():
        folder = os.path.join(OUTPUT_DIR, category)
        os.makedirs(folder, exist_ok=True)

        # Count existing clips in this folder
        existing = [
            f for f in os.listdir(folder)
            if f.endswith(".mp4")
        ] if os.path.isdir(folder) else []
        count = len(existing)

        print(f"\n── {category} ({count} existing) ──")

        for query in queries:
            if is_done(progress, category, query):
                print(f"  ⏭ Skipping (done): {query}")
                continue

            print(f"  Searching: {query}")
            try:
                count = fetch_and_download(category, query, folder, count)
                mark_done(progress, category, query)
                time.sleep(1)   # pause between searches
            except KeyboardInterrupt:
                print(f"\n\n⚠ Interrupted. Progress saved to {PROGRESS_FILE}")
                print(f"   Run again to resume from where you left off.\n")
                return

        print(f"  ✓ Category total: {count} clips")
        total_all += count

    # Clear progress file on full completion
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    print(f"\n{'='*52}")
    print(f"  ✅ Complete — {total_all} clips downloaded")
    print(f"  Location: {OUTPUT_DIR}/")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()