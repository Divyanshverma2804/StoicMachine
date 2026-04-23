From the transcript, here's the full setup to recreate:

## GCP VM Config
- **Machine type:** 4 vCPU, 15GB RAM (likely `n2-standard-4` or `e2-highmem-4` or `e2-standard-4`)
- **OS:** Debian 12 Bookworm
- **Boot disk:** 10GB (keep minimal, Docker moved off it)
- **Data disk:** 100GB standard persistent disk (mounted at `/opt/reelforge`)
- **Firewall rule:** TCP:8000 open (named `allow-reelforge`)

---

## Full Setup Sequence

**1. Format and mount data disk**
```bash
sudo mkfs.ext4 /dev/sdb
sudo mkdir -p /opt/reelforge
sudo mount /dev/sdb /opt/reelforge
echo "/dev/sdb /opt/reelforge ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

**2. Install Docker**
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

**3. Move Docker + containerd storage to 100GB disk**
```bash
sudo systemctl stop docker
sudo systemctl stop containerd

sudo mkdir -p /opt/reelforge/docker-data
sudo mkdir -p /opt/reelforge/docker-data/containerd

# Docker daemon
sudo nano /etc/docker/daemon.json
```
```json
{
  "data-root": "/opt/reelforge/docker-data"
}
```
```bash
# Containerd
sudo nano /etc/containerd/config.toml
```
Add at top:
```toml
root = "/opt/reelforge/docker-data/containerd"
```
```bash
sudo systemctl start containerd
sudo systemctl start docker
```

**4. Clone repo and set up project**
```bash
cd /opt/reelforge
git clone https://github.com/Divyanshverma2804/StoicMachine.git .
mkdir -p data output stock static
```

**5. Add required files (copy from old VM or local)**
- `client_secret.json` — OAuth desktop app credentials
- `data/yt_token.json` — YouTube OAuth token
- `music.mp3` — background music
- `voice_ref_andrew.wav` — Chatterbox voice reference
- Stock images into `stock/`

**6. `.env` file**
```
STOCK_FOLDER=stock
MUSIC_FILE=music.mp3
OUTPUT_FOLDER=output
DB_PATH=data/reelforge.db
FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
FONT_GEORGIA=/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf
FONT_GEORGIA_I=/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf
PAGE_NAME=Silenor
YT_CLIENT_SECRET=client_secret.json
YT_TOKEN_FILE=data/yt_token.json
YT_CATEGORY_ID=22
YT_PRIVACY=private
YT_TAGS=motivation,mindset,philosophy,stoicism
RENDER_MAX_RETRY=3
TTS_EXAGGERATION=0.7
TTS_CFG_WEIGHT=0.3
TTS_VOICE_REF=/app/voice_ref_andrew.wav
TTS_PAUSE_MS=450
```

**7. Add .dockerignore**
```bash
echo "docker-data" > /opt/reelforge/.dockerignore
```

**8. Build and run**
```bash
docker compose up -d --build
```

---

## Cost Warning

The 15GB RAM machine is what ate the $300 — it's not cheap to run 24/7. On the new account consider:

- **Scale down to `e2-standard-2`** (2 vCPU, 8GB RAM) — Chatterbox will still load, just slower rendering (~25 min/reel instead of 15)
- **Or keep `n2-standard-4` but stop the VM** when not actively rendering via a startup/shutdown script
- The 100GB disk is cheap (~$8/month) regardless of VM size, so keep that

Want me to write a startup script that auto-mounts the disk and starts Docker when you spin the VM back up?