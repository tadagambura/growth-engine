#!/usr/bin/env bash
# The whole N95 setup, run from Archie in a normal terminal. Safe to run again.
# You will be asked for the N95 password, and once to sign in to Tailscale (open the link it prints).
#   bash deploy/n95/from-archie.sh
set -euo pipefail
LAN="${N95_LAN:-n95}"               # ssh alias on the home network
TS="${N95_TS:-tada@archie-n95}"     # Tailscale name: the only way in once the firewall is on
SECRETS="$HOME/.config/app-portfolio/secrets.env"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
REPO=https://github.com/tadagambura/growth-maintenance-engine.git
INSTALL='bash ~/growth-maintenance-engine/deploy/n95/install.sh'
[ -f "$SECRETS" ] || { echo "Missing $SECRETS"; exit 1; }

echo "=== Step 1: system, Tailscale, firewall"
if ssh -o BatchMode=yes -o ConnectTimeout=8 "$LAN" true 2>/dev/null; then FIRST="$LAN"; else FIRST="$TS"; fi
ssh -t "${SSH_OPTS[@]}" "$FIRST" "cd ~ && { [ -d growth-maintenance-engine/.git ] && git -C growth-maintenance-engine pull -q --ff-only || git clone -q $REPO; } && $INSTALL"

echo "=== Step 2: copy secrets, then start Postiz"
scp "${SSH_OPTS[@]}" -p "$SECRETS" "$TS:/srv/gme/secrets.env"
ssh -t "${SSH_OPTS[@]}" "$TS" "chmod 600 /srv/gme/secrets.env && $INSTALL"

echo "=== Step 3: video engine and timers"
ssh -t "${SSH_OPTS[@]}" "$TS" 'bash /srv/gme/engine/deploy/n95/install-engine.sh'

echo "=== Step 4: make one test video (posts are only logged)"
ssh -t "${SSH_OPTS[@]}" "$TS" 'cd /srv/gme/engine && set -a && . /etc/gme.env && set +a && .venv/bin/python -m gme run-day --date 2026-12-02'
echo "=== All four steps finished."
