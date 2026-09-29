#!/bin/sh
# Container start-up: wait for PostgreSQL, apply migrations, collect static
# files, optionally load demo data, then start the web server.
set -e

echo "Waiting for database..."
python - <<'PY'
import os, sys, time
import psycopg
url = os.environ.get("DATABASE_URL", "")
for attempt in range(60):
    try:
        psycopg.connect(url, connect_timeout=3).close()
        print("Database is ready.")
        sys.exit(0)
    except Exception as exc:
        time.sleep(1)
print("Database not reachable after 60s", file=sys.stderr)
sys.exit(1)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput -v 0

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  python manage.py seed_demo
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
  python manage.py ensure_admin
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --access-logfile - \
  --timeout 60
