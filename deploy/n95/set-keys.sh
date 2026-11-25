#!/usr/bin/env bash
# Run on Archie, in your own terminal. Asks for the platform app keys, saves them to the secrets
# file here and on the N95, then restarts Postiz. Press Enter to skip any key (its old value stays).
#   bash set-keys.sh                                   all of them
#   bash set-keys.sh YOUTUBE_CLIENT_ID YOUTUBE_CLIENT_SECRET
set -euo pipefail
LOCAL="${KEYS_FILE:-$HOME/.config/app-portfolio/secrets.env}"
HOST="${N95_HOST:-tada@archie-n95}"
KEYS=("$@")
[ ${#KEYS[@]} -gt 0 ] || KEYS=(YOUTUBE_CLIENT_ID YOUTUBE_CLIENT_SECRET META_APP_ID META_APP_SECRET THREADS_APP_ID THREADS_APP_SECRET)
[ -f "$LOCAL" ] || { echo "No secrets file at $LOCAL" >&2; exit 1; }

# Replaces NAME=... lines (or adds them) with the NAME=value lines read from standard input.
# Values never appear in a command line. The same function runs here and on the N95.
merge() {
  local file=$1 tmp line name
  tmp=$(mktemp "$file.XXXXXX"); chmod 600 "$tmp"
  cp "$file" "$tmp"
  while IFS= read -r line; do
    name=${line%%=*}
    { grep -v "^$name=" "$tmp" || true; printf '%s\n' "$line"; } > "$tmp.new"
    cat "$tmp.new" > "$tmp"; rm -f "$tmp.new"
  done
  mv "$tmp" "$file"
}

changes=()
for k in "${KEYS[@]}"; do
  [[ "$k" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "Not a key name: $k" >&2; exit 1; }
  v=""
  read -r -s -p "$k (hidden, Enter to skip): " v || true; echo
  v=$(printf '%s' "$v" | tr -d '[:space:]')
  [ -n "$v" ] || continue
  [[ "$v" =~ ^[A-Za-z0-9._~+/=:-]+$ ]] || { echo "That doesn't look like a key (unexpected characters). Nothing was changed." >&2; exit 1; }
  changes+=("$k=$v")
  echo "  got ${#v} characters"
done
[ ${#changes[@]} -gt 0 ] || { echo "Nothing entered, nothing changed."; exit 0; }

printf '%s\n' "${changes[@]}" | merge "$LOCAL"
echo "Saved ${#changes[@]} key(s) on this PC."
[ "${SKIP_N95:-}" != 1 ] || exit 0
printf '%s\n' "${changes[@]}" | ssh -o ConnectTimeout=10 "$HOST" "$(declare -f merge); set -euo pipefail; merge /srv/gme/secrets.env"
ssh -o ConnectTimeout=10 "$HOST" 'bash /srv/gme/engine/deploy/n95/render-config.sh && gme-compose up -d postiz'
echo "Done: the N95 has the keys and Postiz has restarted."
