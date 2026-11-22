#!/usr/bin/env bash
# Nightly database dumps (the N95 is silent, so night is fine). Keeps 14 days.
set -euo pipefail
GME="${GME_HOME:-/srv/gme}"
OUT="$GME/backups/$(date +%F)"
mkdir -p "$OUT" && chmod 700 "$GME/backups"
docker exec gme-postgres pg_dump -U gme -d gme -Fc > "$OUT/gme.dump"
docker exec postiz-postgres pg_dump -U postiz-user -d postiz-db-local -Fc > "$OUT/postiz.dump"
find "$GME/backups" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "Backed up to $OUT"
