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

## Backup to the Inspiron
Wednesdays and Sundays at noon (London) the N95 copies the videos, plus an encrypted copy of the databases and settings, to the Inspiron (`~/kc-video-backup`), waking it if needed and powering it off again only if it woke it. Run once on the Inspiron: `deploy/inspiron/setup.sh`. Cron line on the N95 (UTC; the script ignores the hour that is not noon in London):
`0 11,12 * * 0,3 bash /srv/gme/engine/deploy/n95/inspiron-backup.sh --if-noon-london >> /srv/gme/data/inspiron-backup.log 2>&1`

### Encrypted databases and settings
The N95 encrypts them to `/srv/gme/backup-cert.pem` (without that file they are skipped, and the log says so). Make the key pair once on Archie, and keep a copy of the private key in your password manager: without it the backups cannot be read.

```
d=~/.config/app-portfolio/backup-keys; mkdir -p $d && chmod 700 $d
openssl req -x509 -newkey rsa:3072 -nodes -days 3650 -subj /CN=gme-backup -keyout $d/gme-backup.key -out $d/gme-backup.pem
scp $d/gme-backup.pem tada@archie-n95:/srv/gme/backup-cert.pem
```

Restore: copy a `gme-state-DATE.tar.gz.cms` from the Inspiron (`~/kc-video-backup/state/`), then
`openssl cms -decrypt -binary -inform DER -in FILE -inkey gme-backup.key | tar -xzf -`.
The `.dump` files load with `pg_restore`.
