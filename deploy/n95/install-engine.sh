#!/usr/bin/env bash
# Installs the video engine as scheduled services on the N95 (after install.sh has run).
#   bash /srv/gme/engine/deploy/n95/install-engine.sh
# Needs /srv/gme/secrets.env (ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
set -euo pipefail
GME=/srv/gme
ENGINE="$GME/engine"
DATA="$GME/data"
[ -f "$GME/secrets.env" ] || { echo "Copy secrets.env to $GME/secrets.env first (see README step 3)"; exit 1; }

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip ffmpeg nodejs npm fonts-liberation
mkdir -p "$DATA"; chmod 700 "$DATA"

cd "$ENGINE"
python3 -m venv .venv
. .venv/bin/activate
pip install -q -e ".[voice]"
( cd render && npm install --silent && npx playwright-core install --with-deps chromium ffmpeg )

# the ElevenLabs SDK reads its key from the engine's own .env (git-ignored)
grep '^ELEVENLABS_API_KEY=' "$GME/secrets.env" > "$ENGINE/.env"; chmod 600 "$ENGINE/.env"
CHROME="$(find "$HOME/.cache/ms-playwright" -type f -name chrome -path '*chromium-*' | head -n 1)"
echo "CHROME_PATH=$CHROME" | sudo tee /etc/gme.env >/dev/null
{ echo "GME_HOME=$DATA"; echo "GME_SECRETS=$GME/secrets.env"; echo "TZ=Europe/London"; } | sudo tee -a /etc/gme.env >/dev/null

run() { cat <<UNIT
[Unit]
Description=Growth engine: $1
OnFailure=gme-alert@%n.service
[Service]
Type=oneshot
User=$USER
WorkingDirectory=$ENGINE
EnvironmentFile=/etc/gme.env
ExecStart=$ENGINE/.venv/bin/python -m gme $2
TimeoutStartSec=1500
Nice=10
UNIT
}
run "make and queue today's video" "run-day" | sudo tee /etc/systemd/system/gme-daily.service >/dev/null
run "publish what is due" "publish-due" | sudo tee /etc/systemd/system/gme-publish.service >/dev/null

sudo tee /etc/systemd/system/gme-daily.timer >/dev/null <<UNIT
[Unit]
Description=Make today's video (06:30 London, 11 hours before it posts)
[Timer]
OnCalendar=*-*-* 06:30:00 Europe/London
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
UNIT
sudo tee /etc/systemd/system/gme-publish.timer >/dev/null <<UNIT
[Unit]
Description=Publish due posts every 10 minutes
[Timer]
OnCalendar=*:0/10
Persistent=true
[Install]
WantedBy=timers.target
UNIT

# tell the owner on Telegram when a run fails (the only time the engine bothers anyone)
sudo tee /etc/systemd/system/gme-alert@.service >/dev/null <<UNIT
[Unit]
Description=Alert: %i failed
[Service]
Type=oneshot
EnvironmentFile=$GME/secrets.env
ExecStart=/bin/sh -c 'curl -s --max-time 20 "https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/sendMessage" --data-urlencode "chat_id=\$TELEGRAM_CHAT_ID" --data-urlencode "text=Growth engine: %i failed on $(hostname). Run: journalctl -u %i -n 50" >/dev/null'
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now gme-daily.timer gme-publish.timer
systemctl list-timers 'gme-*' --no-pager
echo "Done. Test now with:  cd $ENGINE && GME_HOME=$DATA .venv/bin/python -m gme status"
