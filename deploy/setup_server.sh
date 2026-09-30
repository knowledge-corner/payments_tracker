#!/usr/bin/env bash
# =============================================================================
#  Payments Tracker - one-command production server setup
#
#  For a fresh Ubuntu 22.04 / 24.04 server (DigitalOcean, AWS Lightsail,
#  Hetzner, ...). Run as root:
#
#    curl -fsSL https://raw.githubusercontent.com/knowledge-corner/payments_tracker/main/deploy/setup_server.sh -o setup.sh
#    sudo bash setup.sh
#
#  What it does (safe to run again - existing passwords/data are kept):
#    1. Installs Docker, Git, firewall (ports 22/80/443 only), 2 GB swap,
#       automatic security updates, fail2ban (blocks SSH password guessing)
#    2. Asks for your domain + admin login, generates all other secrets
#    3. Starts the app + PostgreSQL + Caddy (automatic HTTPS certificate)
#    4. Schedules a daily database backup at 02:30 (kept 14 days,
#       optionally copied off the server with rclone)
#    5. Installs the `payments` helper command (update, logs, backup, ...)
#
#  Non-interactive use: set APP_DOMAIN, ADMIN_USERNAME, ADMIN_EMAIL,
#  ADMIN_PASSWORD (and optionally LOAD_DEMO=1, REPO_URL, APP_DIR) beforehand.
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/knowledge-corner/payments_tracker.git}"
APP_DIR="${APP_DIR:-/opt/payments_tracker}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/payments_tracker}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.prod.yml"
SKIP_SYSTEM="${SKIP_SYSTEM:-0}"   # 1 = skip OS packages/firewall/swap (used for testing)

bold()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail()  { printf '\n\033[31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

ask() {  # ask VAR "Question" "default" [secret]
  local var="$1" question="$2" default="${3:-}" secret="${4:-}" answer=""
  if [ -n "${!var:-}" ]; then return; fi
  while [ -z "$answer" ]; do
    if [ -n "$secret" ]; then
      read -r -s -p "  $question: " answer; echo
    else
      read -r -p "  $question${default:+ [$default]}: " answer
    fi
    answer="${answer:-$default}"
  done
  printf -v "$var" '%s' "$answer"
}

[ "$(id -u)" -eq 0 ] || fail "Please run as root:  sudo bash $0"

# -----------------------------------------------------------------------------
bold "1/6  Your settings"
ask APP_DOMAIN "Domain for the app (e.g. payments.yourpractice.in)"
APP_DOMAIN="${APP_DOMAIN#http://}"; APP_DOMAIN="${APP_DOMAIN#https://}"; APP_DOMAIN="${APP_DOMAIN%%/*}"
ask ADMIN_USERNAME "Admin username" "admin"
ask ADMIN_EMAIL "Admin email"
if [ -z "${ADMIN_PASSWORD:-}" ]; then
  while :; do
    ask ADMIN_PASSWORD "Admin password (min 10 characters)" "" secret
    [ "${#ADMIN_PASSWORD}" -ge 10 ] || { warn "Too short, try again."; ADMIN_PASSWORD=""; continue; }
    CONFIRM=""; ask CONFIRM "Repeat admin password" "" secret
    [ "$ADMIN_PASSWORD" = "$CONFIRM" ] && break
    warn "Passwords do not match, try again."; ADMIN_PASSWORD=""
  done
fi
if [ -z "${LOAD_DEMO:-}" ]; then
  read -r -p "  Load demo doctors/hospitals/cases? (y/N): " yn
  case "$yn" in [Yy]*) LOAD_DEMO=1 ;; *) LOAD_DEMO=0 ;; esac
fi
ok "Domain: $APP_DOMAIN   Admin: $ADMIN_USERNAME   Demo data: $([ "$LOAD_DEMO" = 1 ] && echo yes || echo no)"

# -----------------------------------------------------------------------------
if [ "$SKIP_SYSTEM" != "1" ]; then
  bold "2/6  Server basics (packages, firewall, swap, time zone)"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git curl ca-certificates ufw fail2ban unattended-upgrades rclone >/dev/null
  ok "Packages installed"

  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh >/dev/null
    ok "Docker installed"
  else
    ok "Docker already installed"
  fi
  systemctl enable --now docker >/dev/null 2>&1 || true
  docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin missing - reinstall Docker."

  if ! swapon --show | grep -q .; then
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -q vm.swappiness=10; echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
    ok "2 GB swap added"
  else
    ok "Swap already present"
  fi

  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
  ok "Firewall on: only SSH, HTTP, HTTPS open"

  systemctl enable --now fail2ban >/dev/null 2>&1 || true
  dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true
  timedatectl set-timezone Asia/Kolkata 2>/dev/null || true
  ok "Automatic security updates, fail2ban, time zone Asia/Kolkata"
else
  bold "2/6  Server basics - skipped (SKIP_SYSTEM=1)"
fi

# -----------------------------------------------------------------------------
bold "3/6  Application code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only -q && ok "Updated code in $APP_DIR"
else
  git clone -q "$REPO_URL" "$APP_DIR" && ok "Downloaded code to $APP_DIR"
fi
cd "$APP_DIR"
git log -1 --date=short --format="  Version: %h  %ad  %s"

# -----------------------------------------------------------------------------
bold "4/6  Configuration (.env)"
if [ -f .env ] && grep -q '^POSTGRES_PASSWORD=' .env; then
  ok ".env already exists - keeping existing secrets and database password"
  # keep domain in sync if it changed
  sed -i "s|^APP_DOMAIN=.*|APP_DOMAIN=$APP_DOMAIN|" .env
else
  # Docker Compose treats "$" in .env as a variable, so escape it as "$$".
  ADMIN_PASSWORD_ENV="${ADMIN_PASSWORD//\$/\$\$}"
  ADMIN_EMAIL_ENV="${ADMIN_EMAIL//\$/\$\$}"
  SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n/+=' | cut -c1-60)"
  DB_PASSWORD="$(openssl rand -base64 32 | tr -d '\n/+=' | cut -c1-32)"
  umask 077
  cat > .env <<EOF
# Generated by deploy/setup_server.sh on $(date '+%Y-%m-%d %H:%M')
APP_DOMAIN=$APP_DOMAIN
DJANGO_SECRET_KEY=$SECRET_KEY
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=$APP_DOMAIN,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://$APP_DOMAIN
DJANGO_SECURE=1
POSTGRES_DB=payments_tracker
POSTGRES_USER=payments
POSTGRES_PASSWORD=$DB_PASSWORD
SEED_DEMO_DATA=$LOAD_DEMO
GUNICORN_WORKERS=2
DJANGO_SUPERUSER_USERNAME=$ADMIN_USERNAME
DJANGO_SUPERUSER_EMAIL=$ADMIN_EMAIL_ENV
DJANGO_SUPERUSER_PASSWORD=$ADMIN_PASSWORD_ENV
EOF
  umask 022
  ok ".env created (secrets generated, file readable by root only)"
fi

# DNS check - Caddy can only get an HTTPS certificate if the domain points here
SERVER_IP="$(curl -fsS -4 --max-time 5 https://api.ipify.org 2>/dev/null || true)"
DOMAIN_IP="$(getent ahostsv4 "$APP_DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)"
if [ -n "$SERVER_IP" ] && [ "$SERVER_IP" = "$DOMAIN_IP" ]; then
  ok "DNS OK: $APP_DOMAIN -> $SERVER_IP"
else
  warn "DNS: $APP_DOMAIN points to '${DOMAIN_IP:-nothing}', this server is '${SERVER_IP:-unknown}'."
  warn "Create an A record for $APP_DOMAIN -> ${SERVER_IP:-<server IP>}. HTTPS starts working a few minutes after DNS updates."
fi

# -----------------------------------------------------------------------------
bold "5/6  Starting the app (first build takes 2-5 minutes)"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up -d --build --remove-orphans
printf '  Waiting for the app to become ready'
READY=0
for _ in $(seq 1 60); do
  # shellcheck disable=SC2086
  if docker compose $COMPOSE_FILES exec -T web python -c \
      "import urllib.request,sys; sys.exit(0 if b'payments-tracker' in urllib.request.urlopen('http://127.0.0.1:8000/health/').read() else 1)" \
      >/dev/null 2>&1; then
    READY=1; break
  fi
  printf '.'; sleep 5
done
echo
if [ "$READY" = 1 ]; then
  ok "App is running (PostgreSQL database, migrations applied)"
else
  # shellcheck disable=SC2086
  docker compose $COMPOSE_FILES logs --tail 40 web
  fail "The app did not start - see the log lines above."
fi
# The admin account now exists; remove its password from .env
sed -i 's/^DJANGO_SUPERUSER_PASSWORD=.*/DJANGO_SUPERUSER_PASSWORD=/' .env

# -----------------------------------------------------------------------------
bold "6/6  Backups and the 'payments' helper command"
mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"
cat > /usr/local/bin/payments <<EOF
#!/usr/bin/env bash
# Payments Tracker helper - run 'payments help'
set -euo pipefail
cd "$APP_DIR"
DC="docker compose $COMPOSE_FILES"
BACKUP_DIR="$BACKUP_DIR"
EOF
cat >> /usr/local/bin/payments <<'EOF'
case "${1:-help}" in
  status)  $DC ps ;;
  logs)    $DC logs -f --tail 100 web ;;
  update)
    git pull --ff-only
    $DC up -d --build --remove-orphans
    git log -1 --date=short --format="Now running: %h  %ad  %s" ;;
  restart) $DC restart web caddy ;;
  backup)
    mkdir -p "$BACKUP_DIR"
    FILE="$BACKUP_DIR/db_$(date +%Y-%m-%d_%H%M).sql.gz"
    $DC exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' | gzip > "$FILE"
    chmod 600 "$FILE"
    find "$BACKUP_DIR" -name 'db_*.sql.gz' -mtime +14 -delete
    echo "Backup saved: $FILE ($(du -h "$FILE" | cut -f1))"
    if [ -f /etc/payments-backup.conf ]; then
      # shellcheck disable=SC1091
      . /etc/payments-backup.conf
      if [ -n "${RCLONE_REMOTE:-}" ]; then
        rclone copy "$FILE" "$RCLONE_REMOTE" && echo "Copied off-server to $RCLONE_REMOTE"
      fi
    fi ;;
  restore)
    FILE="${2:?Usage: payments restore /var/backups/payments_tracker/db_....sql.gz}"
    read -r -p "This REPLACES all current data with $FILE. Type YES to continue: " c
    [ "$c" = "YES" ] || { echo "Cancelled."; exit 1; }
    $DC stop web
    $DC exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
    gunzip -c "$FILE" | $DC exec -T db sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
    $DC start web
    echo "Restored from $FILE" ;;
  createadmin) $DC exec web python manage.py createsuperuser ;;
  shell)   $DC exec web python manage.py shell ;;
  *)
    cat <<'HELP'
payments status       - show running containers
payments logs         - live application logs (Ctrl+C to stop)
payments update       - download latest code, rebuild, apply migrations
payments restart      - restart the app
payments backup       - back up the database now
payments restore FILE - restore the database from a backup file
payments createadmin  - create another admin login
HELP
    ;;
esac
EOF
chmod 755 /usr/local/bin/payments
ok "Helper installed: run 'payments help'"

cat > /etc/cron.d/payments-backup <<'EOF'
# Daily database backup for Payments Tracker (server time)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * root /usr/local/bin/payments backup >> /var/log/payments-backup.log 2>&1
EOF
chmod 644 /etc/cron.d/payments-backup
[ -f /etc/payments-backup.conf ] || cat > /etc/payments-backup.conf <<'EOF'
# Optional off-server copy of the daily backup via rclone.
# 1) run: rclone config   (e.g. add Google Drive as "gdrive")
# 2) set: RCLONE_REMOTE="gdrive:payments-backups"
RCLONE_REMOTE=""
EOF
/usr/local/bin/payments backup >/dev/null && ok "Daily backup at 02:30 scheduled - first backup taken in $BACKUP_DIR"

# -----------------------------------------------------------------------------
bold "Done!"
cat <<EOF
  Open:        https://$APP_DOMAIN
  Admin login: $ADMIN_USERNAME  (the password you entered)

  Next steps:
   - Sign in, open Settings: decide on sign-ups / admin approval
   - Optional off-server backups: edit /etc/payments-backup.conf (see comments)
   - Update to new versions any time:  payments update
EOF
