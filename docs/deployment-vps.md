# VPS Deployment — Shared Contabo Server (`dishari.tourismbangladesh.live`)

Target: a Contabo VPS running Ubuntu 24.04 that already hosts other Docker
stacks (`ruletheday-backend` owns host :80/:443 with its own nginx + certbot;
`movie_reservation_backend` uses :81; `travel-persona` uses :8010). This app
runs as an isolated Docker project and is reverse-proxied by the existing
ruletheday nginx.

```
Internet :80/:443
   └─▶ ruletheday-backend-nginx-1        (theirs; one appended server block)
         ├── ruletheday.app / api.*      (untouched)
         ├── persona.tourismbangladesh.live ──▶ travel-persona-nginx:80   [travel-persona]
         └── dishari.tourismbangladesh.live ──▶ airport-kiosk-nginx:80    [airport-kiosk]
                                                  └─▶ airport-kiosk web:8000 (gunicorn)
                                                         └─▶ SQLite on the sqlite_data volume
```

This stack has **no bundled route on host :80** — the compose `nginx` service
binds `127.0.0.1:8012` only (loopback tests), and the public route is the
snippet appended to the ruletheday nginx.

## 1. DNS (Cloudflare)

1. Get the VPS IP: `curl -4 -s ifconfig.me`
2. Cloudflare dashboard → zone **tourismbangladesh.live** → **DNS** → **Records**
   → **Add record**:
   - **Type:** `A`
   - **Name:** `dishari`
   - **IPv4 address:** `<VPS IP>`
   - **Proxy status:** **DNS only** (grey cloud) — required so the Let's Encrypt
     HTTP-01 challenge reaches the origin directly.
   - **TTL:** Auto
3. Verify: `dig +short dishari.tourismbangladesh.live @1.1.1.1` → the VPS IP.

## 2. First deploy

```bash
mkdir -p /opt/dishari-ai && cd /opt/dishari-ai
git clone https://github.com/shamim565/dishari-ai.git .

# .env (never committed)
nano .env
chmod 600 .env

docker compose -f docker-compose.vps.yml up -d --build
docker compose -f docker-compose.vps.yml logs --tail=50 web   # migrate + collectstatic
```

`.env`:

```
DEBUG=0
SECRET_KEY=<openssl rand -base64 48>
ALLOWED_HOSTS=dishari.tourismbangladesh.live,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://dishari.tourismbangladesh.live
BASE_URL=https://dishari.tourismbangladesh.live
DB_PATH=/data/db.sqlite3
OPS_PIN=<strong pin — replace the 1234 default>
KIOSK_IDLE_SECONDS=120

# Optional — full AI + guaranteed bn-BD voice:
# GEMINI_API_KEY=
# OPENAI_API_KEY=
# VISION_PROVIDER=gemini
# CHAT_PROVIDER=gemini
# AZURE_SPEECH_KEY=
# AZURE_SPEECH_REGION=southeastasia
```

- `localhost,127.0.0.1` are required: the container healthcheck calls
  `http://localhost:8000/health/`.
- `DB_PATH=/data/db.sqlite3` puts the database on the `sqlite_data` volume —
  it survives rebuilds. Without it the DB would live inside the container.
- `BASE_URL` is embedded in the kiosk QR code, so phones anywhere (4G included)
  can open the upload page.
- `DEBUG=0` is required for production; set a real `SECRET_KEY`.

Seed today's demo data and create the admin user:

```bash
docker compose -f docker-compose.vps.yml exec web python manage.py seed_demo
docker compose -f docker-compose.vps.yml exec web python manage.py createsuperuser
```

## 3. Verify the stack internally

```bash
# through our nginx (loopback)
curl -fsS http://127.0.0.1:8012/health/

# through the shared Docker network, simulating the outer proxy
docker exec ruletheday-backend-nginx-1 \
  wget -qO- --header='Host: dishari.tourismbangladesh.live' http://airport-kiosk-nginx/health/
```

Expected: `{"status": "ok", "db": true}`.

## 4. TLS certificate (existing certbot container)

Webroot issuance works before the nginx snippet is added because the
ruletheday :80 catch-all already serves `/.well-known/acme-challenge/`.

```bash
docker exec ruletheday-backend-certbot-1 certbot certonly --webroot \
  -w /var/www/certbot -d dishari.tourismbangladesh.live --non-interactive --agree-tos
ls -l /etc/letsencrypt/live/dishari.tourismbangladesh.live/

# if certbot refuses without an email:
#   ... --non-interactive --agree-tos -m you@example.com
```

The renewal config is written with `authenticator = webroot`, so the container's
12h `certbot renew` loop keeps it valid.

## 5. Route the subdomain through the ruletheday nginx

Their nginx mounts a single config file, so append the snippet (versioned in
this repo at `deploy/vps/ruletheday-snippet.conf`) with a backup first:

```bash
cp /opt/ruletheday-backend/nginx/nginx.conf \
   /opt/ruletheday-backend/nginx/nginx.conf.bak-$(date +%F)

# append the contents of deploy/vps/ruletheday-snippet.conf to nginx.conf
# (to replace an existing block, drop it first between the markers:)
#   sed -i '/# BEGIN airport-kiosk/,/# END airport-kiosk/d' \
#     /opt/ruletheday-backend/nginx/nginx.conf

docker exec ruletheday-backend-nginx-1 nginx -t
docker restart ruletheday-backend-nginx-1
```

`nginx -t` must pass before applying; the appended block only matches
`dishari.tourismbangladesh.live` (exact `server_name` beats their `_`
catch-all). Their sites are unaffected. Restart (not `-s reload`): the config is
a single-file bind mount, so a replaced file keeps its old inode in the
container.

## 6. Verify live

```bash
curl -fsS https://dishari.tourismbangladesh.live/health/
```

Browser checklist:

- Kiosk dashboard opens: voice assistant band on the left, QR ticket panel on
  the right; tap the mic once — HTTPS satisfies the microphone requirement
- Scan the QR with a phone (mobile data is fine — `BASE_URL` is public) →
  upload the demo ticket photo → the kiosk switches to the journey by itself
- `/ops/` accepts the `OPS_PIN`; `/admin/` accepts the superuser login
- Re-check `ruletheday.app` / `api.ruletheday.app` and
  `persona.tourismbangladesh.live` still respond

## 7. Backups + housekeeping (cron)

SQLite is backed up with the Python `sqlite3` online backup API inside the
container (safe while the app runs), then copied out of the volume.

```bash
mkdir -p /opt/dishari-ai-backups
crontab -e
```

```cron
# 03:00 — consistent SQLite backup
0 3 * * * cd /opt/dishari-ai && docker compose -f docker-compose.vps.yml exec -T web python -c "import sqlite3; s=sqlite3.connect('/data/db.sqlite3'); d=sqlite3.connect('/data/db-backup.sqlite3'); s.backup(d); d.close(); s.close()" && docker compose -f docker-compose.vps.yml cp web:/data/db-backup.sqlite3 /opt/dishari-ai-backups/db-$(date +\%F).sqlite3

# 03:15 — kiosk housekeeping (expired journeys, chats, handoffs, sessions)
15 3 * * * cd /opt/dishari-ai && docker compose -f docker-compose.vps.yml exec -T web python manage.py purge_sessions

# 03:20 — retention: keep 14 days
20 3 * * * find /opt/dishari-ai-backups -name 'db-*.sqlite3' -mtime +14 -delete
```

Restore:

```bash
docker compose -f docker-compose.vps.yml stop web
docker compose -f docker-compose.vps.yml cp /opt/dishari-ai-backups/db-<date>.sqlite3 web:/data/db.sqlite3
docker compose -f docker-compose.vps.yml start web
```

## 8. Updates

```bash
cd /opt/dishari-ai
git pull
docker compose -f docker-compose.vps.yml up -d --build
```

`entrypoint.sh` runs migrations and collectstatic on start. `.env` stays
untouched. If `deploy/vps/ruletheday-snippet.conf` changes in the repo, re-apply
the block (replace between the `# BEGIN/# END airport-kiosk` markers) and
restart the ruletheday nginx.

## 9. Demo-day operations

`seed_demo` always seeds **the current date** (Asia/Dhaka) and replaces the old
data, so run it on every demo day:

```bash
docker compose -f docker-compose.vps.yml exec web python manage.py seed_demo
```

Optional — regenerate the demo ticket PNGs inside the container (the files
land in the container's `demo_assets/`; fonts are bundled):

```bash
docker compose -f docker-compose.vps.yml exec web python manage.py make_tickets
```

The ops panel **Reset demo data** button (PIN-gated) re-seeds flights and the
layout too. Note it does **not** regenerate the ticket PNGs — run `make_tickets`
afterwards if you use it on a new day.

## 10. Optional: basic auth for `/ops/` + `/admin/`

Off by default. To add a browser password prompt on top of the PIN / Django login:

```bash
cd /opt/dishari-ai
docker run --rm httpd:alpine htpasswd -nbB <user> '<password>' > .htpasswd
chmod 640 .htpasswd
```

1. Add the mount to the `nginx` service in `docker-compose.vps.yml`:
   `- ./.htpasswd:/etc/nginx/.htpasswd:ro`
2. Add the two `auth_basic*` lines to the `/ops/` and `/admin/` blocks in
   `deploy/vps/kiosk-nginx.conf` (copy them from the travel-persona config
   pattern).
3. Apply: `docker compose -f docker-compose.vps.yml up -d nginx`

Recreate `.htpasswd` before the first `up` — a missing bind-mount source is
created as a directory by Docker and nginx fails to start.

## Troubleshooting

| Symptom                      | Cause / fix                                                                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| `400 DisallowedHost`         | `ALLOWED_HOSTS` missing the domain or `localhost`                                             |
| `502 Bad Gateway`            | `web` container down → `docker compose -f docker-compose.vps.yml ps`, `logs web`              |
| Static 404                   | `collectstatic` failed or static volume not mounted → check `logs web`                        |
| CSRF failure                 | outer proxy not sending `X-Forwarded-Proto`; check `CSRF_TRUSTED_ORIGINS` and the nginx `map` |
| `nginx: [emerg]` on reload   | snippet references a missing cert file — issue the cert first (step 4)                        |
| certbot challenge fails      | DNS not propagated, or Cloudflare proxy is orange — set DNS only                              |
| Phone can't open the QR      | `BASE_URL` must be the public https URL; re-check step 2 and restart                          |
| Voice dead on the kiosk      | microphone requires HTTPS — use the `https://dishari...` URL, not the IP                      |
| basic-auth 500s (if enabled) | `.htpasswd` missing or is a directory — recreate the file (step 10)                           |
