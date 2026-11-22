# Always-on host setup (N95)

Turns a fresh Ubuntu Server LTS mini PC into the engine host: Postiz (self-hosted publisher,
official compose file pinned to a known commit and image v2.26.0), the engine's PostgreSQL,
an optional Cloudflare Tunnel, automatic security updates, a closed firewall and nightly backups.

## 1. Install Ubuntu Server
Bootable USB → Ubuntu Server LTS → default options → tick **Install OpenSSH server**.

## 2. Run the installer (on the N95)
```bash
git clone https://github.com/tadagambura/growth-maintenance-engine.git
bash growth-maintenance-engine/deploy/n95/install.sh
```
It opens a Tailscale login link the first time; sign in with the same account as Archie.
It then stops and asks for the secrets file.

## 3. Copy the secrets file (from Archie) and run it again
```bash
scp ~/.config/app-portfolio/secrets.env <user>@<n95>:/srv/gme/secrets.env
# then on the N95:
bash ~/growth-maintenance-engine/deploy/n95/install.sh
```

## 4. Public HTTPS for Postiz (optional but recommended)
1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → **Create tunnel** (Cloudflared).
2. Copy the token into `CLOUDFLARE_TUNNEL_TOKEN` in the secrets file.
3. Add a public hostname: `postiz.<your domain>` → service `http://postiz:5000`.
4. Zero Trust → Access → Applications → add `postiz.<your domain>` with a policy that allows
   **only your email**. Nobody else can even see the login page.
5. On the N95: `bash /srv/gme/engine/deploy/n95/render-config.sh && gme-compose up -d`

## 5. Lock registration
Create your Postiz login, then set `POSTIZ_DISABLE_REGISTRATION=true` in the secrets file and
re-run step 4.5.

## Everyday commands
| Command | What |
|---|---|
| `gme-compose ps` | Is everything running? |
| `gme-compose logs -f postiz` | Postiz logs |
| `gme-compose pull && gme-compose up -d` | Update to the pinned versions |
| `ls /srv/gme/backups` | Nightly database backups (14 days kept) |

## What's where
| Path | What |
|---|---|
| `/srv/gme/secrets.env` | Your keys (copied from Archie), chmod 600 |
| `/srv/gme/generated.env` | Random passwords generated on first run, kept stable |
| `/srv/gme/.env`, `/srv/gme/postiz.override.yaml` | Rendered from the above; don't edit by hand |
| `/srv/gme/postiz/` | Postiz's official compose files (pinned commit) |
| `/srv/gme/engine/` | This repo |
