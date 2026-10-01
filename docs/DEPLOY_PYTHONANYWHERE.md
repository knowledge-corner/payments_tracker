# Client testing on PythonAnywhere (free, SQLite)

Share a first draft with the client at `https://<username>.pythonanywhere.com`.
No Docker needed. The SQLite database is kept on PythonAnywhere's permanent disk.

| Item | Value |
|---|---|
| Cost | Free "Beginner" account |
| Python version | **3.12** (3.10–3.13 work) |
| Database | SQLite file in `~/payments_tracker/data/db.sqlite3` |
| HTTPS | Included |
| Keep-alive | Log in once every 3 months and click **"Run until 3 months from today"** on the Web tab |
| Limits | 1 web app, 512 MB disk, limited CPU per day: fine for testing, not for production |

> Use demo or test data only. Real patient/payment data should go on the production server.

---

## 1. Create the account

1. Sign up at <https://www.pythonanywhere.com> → **Pricing & signup → Create a Beginner account**.
   Your username becomes the web address, e.g. `anaesthesiapay` → `https://anaesthesiapay.pythonanywhere.com`.

## 2. Get the code (Bash console)

Open **Consoles → Bash** and run (replace nothing, copy as is):

```bash
git clone https://github.com/knowledge-corner/payments_tracker.git
cd payments_tracker
python3.12 -m venv ~/.venvs/payments
source ~/.venvs/payments/bin/activate
pip install -r requirements.txt
```

> Private repository? When Git asks for a password, paste a GitHub **personal access token**
> (GitHub → Settings → Developer settings → Personal access tokens → Fine-grained, read-only access to this repo).

## 3. Settings (`.env` file)

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"   # copy the output
nano .env
```

Set these lines (replace `<username>` with your PythonAnywhere username), then save with **Ctrl+O, Enter, Ctrl+X**:

```env
DJANGO_SECRET_KEY=<paste the random value>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=<username>.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://<username>.pythonanywhere.com
DJANGO_SECURE=0
```

## 4. Create the database and demo data

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_demo          # demo doctors, hospitals, cases (skip for an empty app)
python manage.py createsuperuser    # optional: your own admin login
```

## 5. Create the web app (Web tab)

1. **Web → Add a new web app → Next → Manual configuration** (not "Django") → **Python 3.12**.
2. **Virtualenv:** `/home/<username>/.venvs/payments`
3. **Source code:** `/home/<username>/payments_tracker`
4. **WSGI configuration file:** click the link, delete everything and paste:

   ```python
   import os
   import sys

   path = "/home/<username>/payments_tracker"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
5. **Static files:** URL `/static/` → Directory `/home/<username>/payments_tracker/staticfiles`
6. **Security:** turn on **Force HTTPS**.
7. Click the green **Reload** button and open `https://<username>.pythonanywhere.com`.

Demo logins: `admin / Admin@12345`, `dr.mehta / Demo@12345`, `dr.rao / Demo@12345` (change them before sharing).

## 6. Push notifications (daily task)

PythonAnywhere does not run background jobs, so add one scheduled task:

1. **Tasks** tab → *Scheduled tasks* → time **03:30** (UTC = 9:00 AM India), frequency **Daily**.
2. Command:
   ```
   cd ~/payments_tracker && ~/.venvs/payments/bin/python manage.py send_notifications
   ```
3. Click **Create**.

Doctors turn notifications on in the app: account menu → **Notification settings** → *Turn on for this device*.
On the free plan, morning summaries go out once a day at the task time (doctors choosing a later hour get them the next run).

> Free accounts can only reach whitelisted websites. If the test notification fails with a connection error,
> the push service for that browser is not on PythonAnywhere's whitelist - it works on a paid account or on DigitalOcean.

## 6b. Email for "Forgot password" (optional)

Add to `~/payments_tracker/.env` (Gmail example - needs an App Password), then Reload the web app:
```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=yourpractice@gmail.com
EMAIL_HOST_PASSWORD=<16-character app password>
DEFAULT_FROM_EMAIL=Payments Tracker <yourpractice@gmail.com>
```
Without it, an admin can set a new password for a doctor on the **Doctors** page.

## 7. Updating after new code is pushed

```bash
cd ~/payments_tracker && bash deploy/pythonanywhere_update.sh
```

The script runs `git pull`, installs requirements, applies migrations, collects static files and reloads the site.

## 8. Backup / hand-over to production

- **Backup:** Files tab → `payments_tracker/data/db.sqlite3` → Download.
- **Export for DigitalOcean:** `python manage.py export_data ~/export.json`, then download `export.json`
  from the Files tab (see `DEPLOY_DIGITALOCEAN.md`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Something went wrong" page | Web tab → **Error log** (last lines show the cause) |
| "DisallowedHost" | `DJANGO_ALLOWED_HOSTS` in `.env` must be exactly `<username>.pythonanywhere.com`; then Reload |
| Login says "CSRF verification failed" | `DJANGO_CSRF_TRUSTED_ORIGINS=https://<username>.pythonanywhere.com`; then Reload |
| Page has no styling | Check the Static files mapping (step 5.5) and run `collectstatic` again |
