#!/bin/bash
# deploy.sh — Bootstrap ReelForge on a fresh GCP VM (Ubuntu 22.04 LTS)
# Run once as root: sudo bash deploy.sh
set -e

echo "======================================================"
echo "  ReelForge — GCP VM Deploy Script"
echo "======================================================"

# ── 1. System packages ────────────────────────────────────
apt-get update -qq
apt-get install -y --no-install-recommends \
    docker.io docker-compose-v2 \
    git curl ffmpeg \
    fonts-dejavu-core fonts-liberation \
    imagemagick python3-pip

systemctl enable docker
systemctl start docker

# ── 2. Allow non-root docker (optional) ──────────────────
usermod -aG docker $SUDO_USER 2>/dev/null || true

# ── 3. Clone / copy project ──────────────────────────────
PROJECT_DIR="/opt/reelforge"
mkdir -p "$PROJECT_DIR"

echo ""
echo "→ Copy your project files to $PROJECT_DIR"
echo "  (If cloning from git: git clone <your-repo> $PROJECT_DIR)"
echo ""

# ── 4. Set up .env ────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "→ Created .env from .env.example — edit before starting!"
fi

# ── 5. Firewall: open port 8000 ───────────────────────────
# GCP: also add firewall rule in Console → VPC → Firewall → allow tcp:8000
ufw allow 8000/tcp 2>/dev/null || true

# ── 6. Stock images & music ──────────────────────────────
mkdir -p "$PROJECT_DIR/stock"
echo "→ Place your stock images in $PROJECT_DIR/stock/"
echo "→ Place music.mp3 at $PROJECT_DIR/music.mp3"
echo "→ Place client_secret.json at $PROJECT_DIR/client_secret.json"

# ── 7. YouTube OAuth first-run instructions ──────────────
echo ""
echo "======================================================"
echo "  YOUTUBE OAUTH SETUP (one-time)"
echo "======================================================"
echo "  1. Go to GCP Console → APIs → YouTube Data API v3 → Enable"
echo "  2. Create OAuth 2.0 client (Desktop app) → Download client_secret.json"
echo "  3. Copy client_secret.json to $PROJECT_DIR/"
echo "  4. Start the app, then run:"
echo "     docker compose exec reelforge python -c \\"
echo "       'from app.uploader import _get_credentials; _get_credentials()'"
echo "  5. Follow the auth URL printed — paste the code back"
echo "  6. Token saved to data/yt_token.json — subsequent uploads are automatic"
echo ""

# ── 8. Systemd service for auto-restart on reboot ────────
cat > /etc/systemd/system/reelforge.service <<'EOF'
[Unit]
Description=ReelForge Video Pipeline
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/reelforge
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable reelforge

echo ""
echo "======================================================"
echo "  DONE. Next steps:"
echo "  1. cd $PROJECT_DIR"
echo "  2. Edit .env (set PAGE_NAME, YT_TAGS, etc.)"
echo "  3. Add stock images, music.mp3, client_secret.json"
echo "  4. docker compose up -d --build"
echo "  5. Visit http://<YOUR_VM_IP>:8000"
echo "======================================================"
