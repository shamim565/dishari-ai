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
