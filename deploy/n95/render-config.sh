#!/usr/bin/env bash
# Turn /srv/gme/secrets.env into the files Docker Compose needs. Safe to re-run.
# Writes (all chmod 600): /srv/gme/generated.env, /srv/gme/.env, /srv/gme/postiz.override.yaml
set -euo pipefail
GME="${GME_HOME:-/srv/gme}"
SECRETS="$GME/secrets.env"
GEN="$GME/generated.env"
[[ -f "$SECRETS" ]] || { echo "Missing $SECRETS (copy it from Archie: scp ~/.config/app-portfolio/secrets.env <n95>:$SECRETS)" >&2; exit 1; }
umask 077
get() { grep -E "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2-; }
s() { get "$1" "$SECRETS"; }
rand() { openssl rand -hex 32; }

# Generated once, then kept so passwords stay stable across re-runs.
touch "$GEN"
for k in JWT_SECRET POSTIZ_DB_PASSWORD GME_DB_PASSWORD; do
  [[ -n "$(get "$k" "$GEN")" ]] || echo "$k=$(rand)" >> "$GEN"
done
g() { get "$1" "$GEN"; }

DOMAIN=$(s DOMAIN)
[[ -n "$DOMAIN" ]] || { echo "DOMAIN is empty in $SECRETS" >&2; exit 1; }
URL="https://postiz.$DOMAIN"
TUNNEL=$(s CLOUDFLARE_TUNNEL_TOKEN)

# .env for Compose variable substitution
cat > "$GME/.env" <<ENV
COMPOSE_PROJECT_NAME=gme
COMPOSE_PROFILES=$([[ -n "$TUNNEL" ]] && echo tunnel)
GME_DB_PASSWORD=$(g GME_DB_PASSWORD)
CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL
ENV

q() { printf "'%s'" "${1//\'/\'\'}"; }   # YAML single-quote
cat > "$GME/postiz.override.yaml" <<YAML
services:
  postiz:
    image: ghcr.io/gitroomhq/postiz-app:v2.26.0
    ports: !override
      - "127.0.0.1:4007:5000"
    environment:
      MAIN_URL: $(q "$URL")
      FRONTEND_URL: $(q "$URL")
      NEXT_PUBLIC_BACKEND_URL: $(q "$URL/api")
      JWT_SECRET: $(q "$(g JWT_SECRET)")
      DATABASE_URL: $(q "postgresql://postiz-user:$(g POSTIZ_DB_PASSWORD)@postiz-postgres:5432/postiz-db-local")
      DISABLE_REGISTRATION: $(q "$(s POSTIZ_DISABLE_REGISTRATION || echo false)")
      X_API_KEY: $(q "$(s X_API_KEY)")
      X_API_SECRET: $(q "$(s X_API_SECRET)")
      FACEBOOK_APP_ID: $(q "$(s META_APP_ID)")
      FACEBOOK_APP_SECRET: $(q "$(s META_APP_SECRET)")
      THREADS_APP_ID: $(q "$(s THREADS_APP_ID)")
      THREADS_APP_SECRET: $(q "$(s THREADS_APP_SECRET)")
      YOUTUBE_CLIENT_ID: $(q "$(s YOUTUBE_CLIENT_ID)")
      YOUTUBE_CLIENT_SECRET: $(q "$(s YOUTUBE_CLIENT_SECRET)")
      TIKTOK_CLIENT_ID: $(q "$(s TIKTOK_CLIENT_KEY)")
      TIKTOK_CLIENT_SECRET: $(q "$(s TIKTOK_CLIENT_SECRET)")
      PINTEREST_CLIENT_ID: $(q "$(s PINTEREST_CLIENT_ID)")
      PINTEREST_CLIENT_SECRET: $(q "$(s PINTEREST_CLIENT_SECRET)")
  postiz-postgres:
    environment:
      POSTGRES_PASSWORD: $(q "$(g POSTIZ_DB_PASSWORD)")
YAML
chmod 600 "$GME/.env" "$GME/postiz.override.yaml" "$GEN" "$SECRETS"
echo "Config rendered for $URL$([[ -n "$TUNNEL" ]] && echo ' (with Cloudflare Tunnel)')"
