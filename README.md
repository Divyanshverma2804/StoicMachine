# ReelForge — Automated Reel Pipeline

Paste content script → renders reels one-by-one → uploads to YouTube on schedule.

---

## Directory Layout

```
reelforge/
├── app/
│   ├── main.py          # FastAPI portal (routes, job submission)
│   ├── models.py        # SQLite DB models (ReelJob, JobStatus)
│   ├── scheduler.py     # Background worker: render + upload ticks
│   ├── renderer.py      # MoviePy reel renderer (per-job)
│   ├── uploader.py      # YouTube Data API v3 upload
│   └── templates/
│       └── index.html   # Web portal UI
├── data/                # SQLite DB + YouTube token (auto-created)
├── output/              # Rendered .mp4 files (auto-created)
├── stock/               # ← YOU: add background images here
├── music.mp3            # ← YOU: add background music here
├── client_secret.json   # ← YOU: add from GCP Console
├── .env                 # ← YOU: copy from .env.example and edit
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── deploy.sh            # GCP VM one-shot bootstrap
```

---

## GCP VM Setup (one-time)

### 1. Create VM
- Machine type: `e2-standard-4` (4 vCPU, 16GB) minimum for rendering
- OS: Ubuntu 22.04 LTS
- Boot disk: 100GB+
- Allow HTTP traffic (port 8000 via firewall rule)

### 2. Bootstrap
```bash
git clone <your-repo> /opt/reelforge
cd /opt/reelforge
sudo bash deploy.sh
```

### 3. Configure
```bash
cp .env.example .env
nano .env          # Set PAGE_NAME, YT_TAGS, etc.
```

### 4. Add assets
```bash
# Upload stock images
scp -r ./stock/* user@VM_IP:/opt/reelforge/stock/

# Upload music
scp music.mp3 user@VM_IP:/opt/reelforge/music.mp3

# Upload YouTube OAuth secret (from GCP Console)
scp client_secret.json user@VM_IP:/opt/reelforge/client_secret.json
```

### 5. YouTube OAuth (one-time)
In GCP Console:
1. APIs & Services → Enable **YouTube Data API v3**
2. OAuth consent screen → External → add your email as test user
3. Credentials → Create → OAuth 2.0 Client ID → **Desktop app** → Download JSON → rename to `client_secret.json`

On the VM (with app stopped):
```bash
cd /opt/reelforge
python yt_auth.py
# Opens browser auth flow → paste code → token saved to data/yt_token.json
```

### 6. Start
```bash
docker compose up -d --build

# Check logs
docker compose logs -f
```

Visit: `http://<VM_EXTERNAL_IP>:8000`

---

## Daily Usage

1. Open the portal
2. Paste your `content.md` into the textarea
3. Optionally set a global upload time (e.g. tomorrow 9am)
4. Click **Queue Reels**
5. The scheduler renders jobs one-by-one in the background
6. Once rendered, jobs with an upload time auto-upload to YouTube
7. Failed jobs show the error and a **Retry** button

---

## Job Lifecycle

```
pending → rendering → rendered → uploading → done
                  ↘              ↗
                   failed (retry up to 3x)
```

- **pending**: waiting in queue
- **rendering**: MoviePy is actively rendering this reel
- **rendered**: .mp4 file exists, waiting for upload time
- **uploading**: being sent to YouTube
- **done**: live on YouTube (video ID shown)
- **failed**: error message shown, retry available

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PAGE_NAME` | `Silenor` | Shown in outro |
| `STOCK_FOLDER` | `stock` | Background images directory |
| `MUSIC_FILE` | `music.mp3` | Background music path |
| `OUTPUT_FOLDER` | `output` | Rendered video output |
| `FONT_PATH` | DejaVu Bold | Main subtitle font |
| `TTS_VOICE` | `en-US-AndrewNeural` | Edge TTS voice |
| `TTS_RATE` | `-12%` | Speech rate |
| `TTS_PITCH` | `-3Hz` | Speech pitch |
| `YT_PRIVACY` | `public` | `public` / `unlisted` / `private` |
| `YT_TAGS` | `motivation,...` | Comma-separated YouTube tags |
| `RENDER_MAX_RETRY` | `3` | Max retries before marking failed |

---

## Security Note

The portal has no authentication by default. On GCP, either:
- Restrict access via firewall rules (allow only your IP)
- Or add HTTP Basic Auth via nginx reverse proxy in front of uvicorn
