#!/usr/bin/env bash
# Copy the video originals from the N95 to the Inspiron. Cron runs it on Wednesdays and Sundays at noon (London).
# Wakes the Inspiron if it is off, and powers it off again only if this script woke it.
#   bash inspiron-backup.sh [--if-noon-london]
set -euo pipefail
GME=/srv/gme
HOST="${BACKUP_HOST:-192.168.1.126}"; WHO="${BACKUP_USER:-tada}"; MAC="${BACKUP_MAC:-8c:ec:4b:b4:f7:c5}"
SSH="ssh -i $HOME/.ssh/inspiron_backup_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
if [ "${1:-}" = "--if-noon-london" ] && [ "$(TZ=Europe/London date +%H)" != 12 ]; then exit 0; fi

alert() {
  local t c
  t=$(grep '^TELEGRAM_BOT_TOKEN=' "$GME/secrets.env" | cut -d= -f2-); c=$(grep '^TELEGRAM_CHAT_ID=' "$GME/secrets.env" | cut -d= -f2-)
  [ -n "$t" ] && [ -n "$c" ] && curl -s -m 20 "https://api.telegram.org/bot$t/sendMessage" --data-urlencode "chat_id=$c" --data-urlencode "text=$1" >/dev/null || true
}
up() { timeout 3 bash -c "</dev/tcp/$HOST/22" 2>/dev/null; }
trap 'alert "Inspiron backup failed. Log: /srv/gme/data/inspiron-backup.log"' ERR

woke=no
if ! up; then
  woke=yes
  python3 -c 'import socket,sys; m=bytes.fromhex(sys.argv[1].replace(":","")); s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1); [s.sendto(b"\xff"*6+m*16,("192.168.1.255",9)) for _ in range(3)]' "$MAC"
  for _ in $(seq 1 60); do up && break; sleep 5; done
  up || { echo "$(date -Is) Inspiron did not wake"; alert "Inspiron backup skipped: it did not wake up."; exit 1; }
fi
rsync -a --partial -e "$SSH" "$GME/data/videos/" "$WHO@$HOST:videos/"
echo "$(date -Is) copied videos (woken: $woke)"
if [ "$woke" = yes ]; then $SSH "$WHO@$HOST" poweroff || true; fi
