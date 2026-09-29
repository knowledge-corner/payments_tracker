#!/bin/bash
# Update the PythonAnywhere deployment: bash deploy/pythonanywhere_update.sh
set -e
cd "$(dirname "$0")/.."
source ~/.venvs/payments/bin/activate

echo "==> Pulling latest code"
git pull --ff-only
echo "==> Installing requirements"
pip install -q -r requirements.txt
echo "==> Applying database migrations"
python manage.py migrate --noinput
echo "==> Collecting static files"
python manage.py collectstatic --noinput -v 0

# Touching the WSGI file reloads the web app on PythonAnywhere.
WSGI_FILE="/var/www/$(whoami)_pythonanywhere_com_wsgi.py"
if [ -f "$WSGI_FILE" ]; then
  touch "$WSGI_FILE"
  echo "==> Web app reloaded"
else
  echo "==> Reload the web app from the Web tab"
fi
git log -1 --date=short --format="Now running: %h  %ad  %s"
