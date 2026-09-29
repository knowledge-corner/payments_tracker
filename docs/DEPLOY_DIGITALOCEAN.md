# Production on DigitalOcean (PostgreSQL + HTTPS)

After the client approves, move from the SQLite test site to a DigitalOcean server with PostgreSQL,
your own domain and automatic HTTPS. All test data can be carried over.

| Item | Recommendation |
|---|---|
| Server | Droplet, **Ubuntu 24.04 with Docker** (Marketplace image), Basic 1 GB / 1 vCPU is enough to start; Bangalore region (BLR1) |
| Database | PostgreSQL 16 in Docker (included), or DigitalOcean Managed PostgreSQL (automatic backups) |
| HTTPS | Caddy (included) gets and renews Let's Encrypt certificates automatically |
| Python | 3.12 (inside the Docker image) |

---

## 1. Prepare

1. Create the Droplet and note its IP address. Enable **backups** (small extra cost).
2. At your domain registrar add an **A record**, e.g. `payments.yourdomain.com → <droplet IP>`.
3. On the **old (SQLite) site**, export the data:
   - PythonAnywhere: `cd ~/payments_tracker && source ~/.venvs/payments/bin/activate && python manage.py export_data ~/export.json`, then download `export.json` (Files tab).
   - Local Docker: `docker compose exec web python manage.py export_data /app/data/export.json` and
     `docker compose cp web:/app/data/export.json ./export.json`

## 2. Install on the Droplet

```bash
ssh root@<droplet IP>
git clone https://github.com/knowledge-corner/payments_tracker.git
cd payments_tracker
cp .env.example .env
nano .env
```

Production `.env` (leave `DJANGO_SUPERUSER_*` empty until the import is done):

```env
APP_DOMAIN=payments.yourdomain.com
DJANGO_SECRET_KEY=<long random value>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=payments.yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://payments.yourdomain.com
DJANGO_SECURE=1
SEED_DEMO_DATA=0
POSTGRES_DB=payments_tracker
POSTGRES_USER=payments
POSTGRES_PASSWORD=<strong password>
# Using DigitalOcean Managed PostgreSQL instead? Set this and leave out docker-compose.postgres.yml:
# DATABASE_URL=postgres://doadmin:<password>@<host>:25060/defaultdb?sslmode=require
```

Start (PostgreSQL + app + HTTPS):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.prod.yml up -d --build
```

## 3. Import the test data

Upload `export.json` to the Droplet (e.g. `scp export.json root@<droplet IP>:~/payments_tracker/`), then:

```bash
C="docker compose -f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.prod.yml"
$C cp export.json web:/app/data/import.json
$C exec web python manage.py loaddata /app/data/import.json
```

Open `https://payments.yourdomain.com` and log in with the same usernames/passwords as on the test site.
Starting fresh instead? Skip this step and run `$C exec web python manage.py createsuperuser`.

## 4. Operations

```bash
# Update to the latest code (migrations run automatically on start)
git pull && $C up -d --build

# Daily database backup (add to crontab: crontab -e)
0 2 * * * cd /root/payments_tracker && docker compose -f docker-compose.yml -f docker-compose.postgres.yml exec -T db pg_dump -U payments payments_tracker | gzip > /root/backup_$(date +\%F).sql.gz
```

## Checklist before go-live

- [ ] Demo users removed or passwords changed
- [ ] `DJANGO_SECURE=1`, strong `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`
- [ ] Droplet backups or the daily `pg_dump` cron enabled
- [ ] Client's phones: open the new address and **Install app** / **Add to Home Screen** again
