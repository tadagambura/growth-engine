#!/usr/bin/env bash
# Run once on the Inspiron, as the user that receives backups (tada). Lets the N95 do two things only:
# write files into ~/kc-video-backup, and power the machine off.
set -euo pipefail
KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHd5FYWNT77/3f8WwaHLP8NWhKqq6YEhHH4e2zK4Bw3e gme-n95-backup'
command -v rrsync >/dev/null || { echo "rrsync is missing: sudo apt-get install -y rsync"; exit 1; }
mkdir -p "$HOME/kc-video-backup" "$HOME/.local/bin" "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
cat > "$HOME/.local/bin/kc-backup-gate" <<'GATE'
#!/bin/sh
case "$SSH_ORIGINAL_COMMAND" in
  poweroff) exec sudo -n /usr/bin/systemctl poweroff ;;
  *) exec rrsync -wo "$HOME/kc-video-backup" ;;
esac
GATE
chmod 755 "$HOME/.local/bin/kc-backup-gate"
touch "$HOME/.ssh/authorized_keys"; chmod 600 "$HOME/.ssh/authorized_keys"
grep -qF "$KEY" "$HOME/.ssh/authorized_keys" || { [ -z "$(tail -c1 "$HOME/.ssh/authorized_keys")" ] || echo >> "$HOME/.ssh/authorized_keys"
  echo "restrict,command=\"$HOME/.local/bin/kc-backup-gate\" $KEY" >> "$HOME/.ssh/authorized_keys"; }
echo "Done. Backups will arrive in $HOME/kc-video-backup."
