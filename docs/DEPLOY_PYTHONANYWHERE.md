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

## 4. Create the database

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser    # your admin login
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

Doctors sign up with **Create an account** on the sign-in page. The starter list of Pune / Mumbai hospitals is loaded by `migrate`; to add the full government directory, upload the data.gov.in CSV under **account menu → Hospital directory**.

## 6. Push notifications (reminder sender)

PythonAnywhere does not run background jobs, so something must start the reminder sender.
Without it, **Send a test** works but scheduled reminders never go out.
**Notification settings** in the app shows "Reminder sender is running" once this is set up.

**Option A - hourly via a free online scheduler (recommended, works on every plan)**

1. Make a long random token: in a Bash console run `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`.
2. Add it to `~/payments_tracker/.env`: `NOTIFICATIONS_CRON_TOKEN=<the token>` and **Reload** the web app.
3. Create a free account at [cron-job.org](https://cron-job.org) → *Create cronjob*:
   URL `https://<username>.pythonanywhere.com/notifications/cron/<the token>/`, schedule **every hour**, save.
4. Open the URL once in a browser: it should show `{"ok": true, ...}`.

**Option B - PythonAnywhere scheduled task**

1. **Tasks** tab → *Scheduled tasks*. Paid accounts: frequency **Hourly**. Free accounts: **Daily** at **03:30**
   (UTC = 9:00 AM India - doctors who chose a later notification time get reminders the next day).
2. Command:
   ```
   cd ~/payments_tracker && ~/.venvs/payments/bin/python manage.py send_notifications
   ```

Doctors turn notifications on in the app: account menu → **Notification settings** → *Turn on for this device*.
To see why someone did or did not get a notification:
```
cd ~/payments_tracker && ~/.venvs/payments/bin/python manage.py check_notifications <username> --send-test
```

> Free accounts can only reach whitelisted websites. If the test notification fails with a connection error,
> the push service for that browser is not on PythonAnywhere's whitelist - it works on a paid account or on DigitalOcean.

## 6b. "Forgot password"

No email setup is needed. **Forgot password?** asks for the user ID and the registered mobile number;
if they match, a new password is set on the spot. **Forgot user ID?** shows the user ID for a registered
mobile number. 5 wrong attempts lock the form for 15 minutes. Admin logins without a doctor profile
reset with `python manage.py changepassword <username>`.

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
