#!/bin/sh
# Container start-up: wait for PostgreSQL (if used), apply migrations, collect static
# files, optionally load demo data, then start the web server.
set -e

case "${DATABASE_URL:-}" in
  postgres*)
    echo "Waiting for PostgreSQL..."
    python - <<'PY'
import os, sys, time
import psycopg
url = os.environ["DATABASE_URL"]
for attempt in range(60):
    try:
        psycopg.connect(url, connect_timeout=3).close()
        print("Database is ready.")
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("Database not reachable after 60s", file=sys.stderr)
sys.exit(1)
PY
    ;;
  *)
    echo "Using SQLite database in ${DATA_DIR:-/app/data}"
    ;;
esac

python manage.py migrate --noinput
python manage.py collectstatic --noinput -v 0

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  python manage.py seed_demo
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
  python manage.py ensure_admin
fi

# Push notifications: check hourly in the background (morning summary, follow-ups, ...).
if [ "${NOTIFICATIONS_SCHEDULER:-1}" = "1" ]; then
  (
    sleep 120
    while true; do
      python manage.py send_notifications --quiet || true
      sleep 3600
    done
  ) &
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --access-logfile - \
  --timeout 60
