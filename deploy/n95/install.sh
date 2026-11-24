#!/usr/bin/env bash
# One-time setup of the always-on engine host (fresh Ubuntu Server LTS).
# Run as your normal user with sudo rights:
#   git clone https://github.com/tadagambura/growth-maintenance-engine.git
#   bash growth-maintenance-engine/deploy/n95/install.sh
set -euo pipefail
GME=/srv/gme
POSTIZ_COMPOSE_REPO=https://github.com/gitroomhq/postiz-docker-compose.git
POSTIZ_COMPOSE_COMMIT=dd4969e5e694cd009619a0d53cff14c21104580b   # pinned 2026-11-22
ENGINE_REPO=https://github.com/tadagambura/growth-maintenance-engine.git

echo "== 1/6 System packages and automatic security updates"
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2 git curl openssl ufw unattended-upgrades
sudo systemctl enable --now docker unattended-upgrades
sudo usermod -aG docker "$USER"

echo "== 2/6 Tailscale (private network to Archie and your phone)"
if ! command -v tailscale >/dev/null; then curl -fsSL https://tailscale.com/install.sh | sh; fi
if ! tailscale ip -4 >/dev/null 2>&1; then sudo tailscale up --ssh; fi   # prints a login link the first time
# The firewall below closes SSH on the home network, so never turn it on without a working tailnet.
tailscale ip -4 >/dev/null 2>&1 || { echo "Tailscale is not connected. Sign in, then re-run this script."; exit 1; }

echo "== 3/6 Firewall: nothing open to the internet; SSH only over Tailscale"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
sudo ufw --force enable

echo "== 4/6 Folders and code"
sudo mkdir -p "$GME" && sudo chown "$USER":"$USER" "$GME" && chmod 700 "$GME"
[[ -d "$GME/engine/.git" ]] || git clone "$ENGINE_REPO" "$GME/engine"
if [[ ! -d "$GME/postiz/.git" ]]; then
  git clone "$POSTIZ_COMPOSE_REPO" "$GME/postiz"
  git -C "$GME/postiz" checkout -q "$POSTIZ_COMPOSE_COMMIT"
fi
sudo install -m 755 "$GME/engine/deploy/n95/gme-compose" /usr/local/bin/gme-compose

echo "== 5/6 Secrets"
if [[ ! -f "$GME/secrets.env" ]]; then
  echo "Copy your secrets file from Archie, then re-run this script:"
  echo "  scp ~/.config/app-portfolio/secrets.env $USER@$(hostname):$GME/secrets.env"
  exit 0
fi
bash "$GME/engine/deploy/n95/render-config.sh"

echo "== 6/6 Start everything, plus nightly backups"
sg docker -c "gme-compose pull && gme-compose up -d"   # sg: docker group without logging out
sudo tee /etc/systemd/system/gme-backup.service >/dev/null <<UNIT
[Unit]
Description=GME database backup
[Service]
Type=oneshot
User=$USER
ExecStart=/bin/bash $GME/engine/deploy/n95/backup.sh
UNIT
sudo tee /etc/systemd/system/gme-backup.timer >/dev/null <<UNIT
[Unit]
Description=Nightly GME database backup
[Timer]
OnCalendar=*-*-* 03:30
Persistent=true
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now gme-backup.timer
echo
echo "Done. Postiz: http://127.0.0.1:4007 on the N95, or https://postiz.<your domain> once the tunnel is set."
echo "Check status any time with: gme-compose ps"
