# Payments Tracker for Anaesthesia Professionals

A mobile-first Django web app (installable as a PWA) that helps anaesthesiologists track
**completed cases → billing → payments → outstanding → follow-ups → reports**.

> Scope: this is a work and payment tracker, **not** a clinical EMR. Only a minimal
> case/patient reference is stored (IP number, bill number or initials).

---

## Table of contents

1. [Quick start on Windows (Docker, one click)](#1-quick-start-on-windows-docker-one-click)
2. [First sign-in and the hospital directory](#2-first-sign-in-and-the-hospital-directory)
3. [Using the app on your phone](#3-using-the-app-on-your-phone)
4. [Everyday commands](#4-everyday-commands)
5. [Features (V1)](#5-features-v1)
6. [Architecture](#6-architecture)
7. [Data model](#7-data-model)
8. [Business rules](#8-business-rules)
9. [Deploying on a domain with HTTPS](#9-deploying-on-a-domain-with-https)
10. [Developing without Docker](#10-developing-without-docker)
11. [Future roadmap](#11-future-roadmap)

---

## 1. Quick start on Windows (Docker, one click)

### One-time setup

| Step | What to do |
|---|---|
| 1 | Install **Docker Desktop**: <https://www.docker.com/products/docker-desktop/> (accept the WSL 2 option if asked, then restart your PC). |
| 2 | Open Docker Desktop once and wait until it shows **Engine running**. Optional: in *Settings → General*, tick **Start Docker Desktop when you sign in**. |
| 3 | Install **Git for Windows**: <https://git-scm.com/download/win> (or use GitHub Desktop). |
| 4 | Get the code, e.g. in *Command Prompt*: `git clone https://github.com/knowledge-corner/payments_tracker.git` (or use **Code → Download ZIP** on GitHub and unzip). |

### Every time you want to use it

1. Open the `payments_tracker` folder.
2. **Double-click `start_app.bat`**.
   - It **downloads the latest code from GitHub (`git pull`)**, starts Docker Desktop if needed, creates `.env`
     on first run, builds and starts the app, waits until the app is healthy,
     **applies database migrations**, then opens **http://localhost:8010** in your browser.
   - If another program already uses port 8010, it picks the next free port automatically and saves it in `.env`.
   - The first run downloads images and can take 3 to 5 minutes. After that it takes a few seconds.
3. When finished, double-click **`stop_app.bat`**. Your data is kept.

> Tip: right-click `start_app.bat` → **Send to → Desktop (create shortcut)** to start the app from your desktop.

| File | Purpose |
|---|---|
| `start_app.bat` | Update the code (git pull), start everything, apply migrations and open the browser |
| `stop_app.bat` | Stop the containers (data is kept) |
| `view_logs.bat` | Watch live application logs (useful if something fails) |
| `reset_all_data.bat` | **Delete all local data** (logins included) and restart empty (asks you to type `YES`) |

### Troubleshooting

| Problem | Fix |
|---|---|
| The browser shows a **different app** (another project that uses the same port) | Run `git pull`, then `start_app.bat`. The launcher now uses port **8010**, detects ports taken by other programs, and moves to a free one. If you have an older `.env` with `APP_PORT=8000`, change it to `APP_PORT=8010` (or delete `.env` so it is recreated). |
| The browser still shows the other app's page | That app's cached page was opened. Use the address `start_app.bat` prints (e.g. `http://localhost:8010`) and press **Ctrl+F5**. |
| "docker compose failed" | Open Docker Desktop and wait for *Engine running*, then run `start_app.bat` again. `view_logs.bat` shows details. |
| Login says "CSRF verification failed" | You opened the app via an address not listed in `.env`. Add it to `DJANGO_CSRF_TRUSTED_ORIGINS` (see section 3). |

### Getting code updates

Nothing to do: every time you double-click `start_app.bat` it runs `git pull`, rebuilds the app and applies any new
database migrations. If the update cannot be downloaded (no internet, or files edited locally), it says so and
starts the version already on your computer.

---

## 2. First sign-in and the hospital directory

The app starts empty apart from the **hospital directory** (about 90 well-known Pune and Mumbai
hospitals) and a list of **departments**.

1. Doctors tap **Create an account** on the sign-in page.
2. For an admin login run `docker compose exec web python manage.py createsuperuser`.
3. *(Admin, optional)* Load the full government list: download the CSV of the
   [Hospital Directory (National Health Portal)](https://data.gov.in/catalog/hospital-directory-national-health-portal)
   from data.gov.in, then **account menu → Hospital directory → Import**
   (or `python manage.py import_hospitals --file hospitals.csv`). Only Pune / Mumbai rows are kept by default;
   re-importing updates rows instead of duplicating them.

How the data fits together:

| Item | Shared or private | Notes |
|---|---|---|
| Hospitals | Shared directory | Doctors can add a missing hospital (duplicate check, marked *unverified* until an admin verifies or merges it) |
| Departments | Shared list | Optional on each case |
| Contacts | **Private per doctor** | One person can be linked to several hospitals / departments; the call button picks the best match |
| Fee, expected payment date | Per case | Nothing is pre-filled; if no date is given the app assumes 30 days (Settings) |

The Django admin panel is at `/admin/` (admin users only).

**Dictate this case (beta add-on).** Add Case has a mic: the doctor says e.g. *"Ruby Hall, ortho, TKR under
spinal, IP 4521, fee 6500, yesterday, payment in 15 days, contact Patil"* and the form is filled in for checking.
It uses the phone's built-in speech recognition (no cost). Turn it off with `FEATURE_DICTATION=0` in `.env`,
or remove it completely by deleting the `dictation/` folder - no database changes are involved.

---

## 3. Using the app on your phone

### On the same Wi-Fi (local testing)

1. Find your PC's IP address: run `ipconfig` in Command Prompt and look for *IPv4 Address*, e.g. `192.168.1.25`.
2. Add it to `.env` so logins from the phone are accepted, then run `start_app.bat` again:
   `DJANGO_CSRF_TRUSTED_ORIGINS=http://192.168.1.25:8010`
3. On the phone, open `http://192.168.1.25:8010`.
4. If Windows Firewall asks, allow Docker Desktop on **private networks**.

### Installing as an app (PWA)

| Phone | Steps |
|---|---|
| **iPhone (Safari)** | Open the site → **Share** → **Add to Home Screen** → Add |
| **Android (Chrome)** | Open the site → menu **⋮** → **Install app** / **Add to Home screen** (or *Install app* in the account menu) |

> Browsers allow full PWA install (service worker, offline page) only on **HTTPS** or `localhost`.
> Over plain `http://192.168.x.x` you can still use the site and add it to the home screen. Full install
> works once the app is deployed on a domain with HTTPS (section 9).

---

## 4. Everyday commands

If you prefer the terminal, run these from the project folder:

```bash
docker compose up -d --build                                   # start
docker compose down                                            # stop (keep data)
docker compose logs -f web                                     # logs
docker compose exec web python manage.py createsuperuser       # create your own admin
docker compose exec web python manage.py reset_app_data --yes   # wipe cases/payments/contacts, keep logins
docker compose exec web python manage.py test                  # run the test suite
docker compose down -v                                         # stop and DELETE the database
```

---

## 5. Features (V1)

| Module | What it does |
|---|---|
| **Dashboard** | Total earnings, amount received, outstanding, cases this month, pending, overdue and follow-ups due. **Action Required** list with one-tap *Paid*, *Follow-up* and *Call*. Quick actions: + Add Case, Record Payment, View Outstanding, View Reports. Period chips: This month, This FY (Apr–Mar), All time. |
| **Add Case** | Built to take under a minute: type-to-search hospital box (matches any part of the name), remembers the last hospital, fills in the hospital's default fee (editable), suggests procedures, has an optional *Payment already received* switch, and *Save & add another*. |
| **Excel import** | *Cases → Import Excel*: download a template (hospital dropdown, payment mode list, instructions), fill it in, upload. A preview shows what will be imported, flags errors row by row, skips duplicates and can create new hospitals (but never a look-alike of an existing one, e.g. a typo). Optional Amount Received / Payment Date / Mode columns create payments too. Existing sheets with headings like "Date", "Hospital Name", "Amount", "IP No" are recognised. |
| **Cases** | Search and filter by status, month and hospital. Case detail shows payments, follow-ups and reminder status. |
| **Payments** | Kept separate from cases: multiple or partial payments, different dates and modes (UPI, NEFT, cheque, cash, card). Over-payment is blocked. |
| **Receivables** | Total outstanding, overdue amount, follow-ups due and an ageing breakdown (0-30 / 31-60 / 61-90 / 90+ days). Sort by oldest first (default), highest amount or hospital. Mark as followed up, snooze (3 days / 1 week / 2 weeks), or log a follow-up with date, method, contact, notes and promised payment date. |
| **Hospitals** | Master data: name, city/address, contact person and number, default fee, payment terms, active/inactive. Shows outstanding per hospital. |
| **Reports** | Monthly summary (cases, earnings, received, outstanding), hospital-wise billing and outstanding, payment history. Every report downloads as CSV for Excel. |
| **Admin** | Manage doctors (with logins), hospitals and settings (payment terms, reminder days). Filter every screen by doctor. |
| **PWA** | Manifest, icons, service worker, offline page, iOS home-screen support. |

### Roles

| | Admin | Doctor |
|---|---|---|
| See data | All doctors (with a doctor filter) | Own cases, payments and follow-ups only |
| Cases / payments / follow-ups | Yes (chooses the doctor) | Yes (own) |
| Hospitals | Add, edit, deactivate | Add and edit |
| Doctors and settings | Yes | No |

---

## 6. Architecture

```
Browser / installed PWA (Bootstrap 5, mobile-first, bottom navigation)
        │  HTTPS (Caddy in production)
        ▼
Django 5.1 on Python 3.12 (gunicorn + whitenoise)  ──►  SQLite (client testing) or PostgreSQL 16 (production)
  ├── accounts/    User (role) + Doctor profile, doctor management
  ├── hospitals/   Hospital master
  ├── cases/       Case model + queryset annotations (paid / outstanding / status)
  ├── payments/    Payment, PaymentFollowUp, receivables + reminder engine (services.py)
  ├── dashboard/   Home screen
  ├── reports/     Monthly, hospital-wise, payment history (+ CSV)
  └── core/        Settings, permissions, PWA endpoints, reset_app_data command, template filters
```

- **Ready for a REST API / native app:** business rules live in model querysets (`Case.objects.with_totals()`)
  and `payments/services.py`, not in views or templates. A future Django REST Framework layer can reuse them directly.
- **No CDN dependency:** Bootstrap and Bootstrap Icons are stored under `static/vendor/`.
- **Database:** SQLite by default (one file in `data/`, or the Docker volume `appdata`). Setting `DATABASE_URL=postgres://...`
  switches to PostgreSQL with no code changes. `manage.py export_data` moves all data across (see section 9).
- **Python:** 3.12 in Docker; 3.10–3.13 supported (Django 5.1).
- **Money** uses `Decimal`, and amounts are shown in Indian format (₹12,34,567).

---

## 7. Data model

| Entity | Key fields |
|---|---|
| `User` | Django user + `role` (admin / doctor) |
| `Doctor` | user, display name, phone, registration no., specialisation, active |
| `Hospital` | name, city, address, contact person/number, default fee, payment terms (days), active |
| `Case` | doctor, hospital, case date, case/patient ref, procedure type, fee, due date, notes, snoozed-until, timestamps |
| `Payment` | case, amount, payment date, mode, reference no., notes |
| `PaymentFollowUp` | case, date, method, contact person, notes, promised payment date |
| `AppSettings` | practice name, default payment terms, reminder days (e.g. `7,14,21`), repeat interval |

`Case`, `Payment` and `Hospital` also carry `source` (manual/import) and `legacy_ref`, so Excel rows can be
imported later without creating duplicates.

---

## 8. Business rules

- **Outstanding** = Case fee − Sum of payments received.
- **Status** is calculated, never typed in:

| Status | Rule |
|---|---|
| Paid | Outstanding ≤ 0 |
| Overdue | Outstanding > 0 and today is past the due date |
| Partially Paid | Some payment received, not yet overdue |
| Pending | Nothing received, not yet overdue |

- **Due date** = case date + hospital payment terms (or the global default of 30 days). It can be changed per case.
- **Follow-up reminders:** a reminder becomes due when an unpaid case reaches each configured age
  (default 7, 14 and 21 days after the case date), then repeats every 7 days. Logging a follow-up clears it.
  Snoozing, or recording a *promised payment date*, pauses it until that date.
  Admins change these under **Settings**.
- No automated WhatsApp or SMS in V1. "WhatsApp (manual)" can be logged as a follow-up method.

---

## 9. Hosting

| Stage | Where | Database | Guide |
|---|---|---|---|
| **Client testing (free)** | PythonAnywhere free account: `https://<username>.pythonanywhere.com` | SQLite | [docs/DEPLOY_PYTHONANYWHERE.md](docs/DEPLOY_PYTHONANYWHERE.md) |
| **Production (after approval)** | DigitalOcean Droplet (~$7/month), your domain with HTTPS, **one-command setup** (`deploy/setup_server.sh`) | PostgreSQL | [docs/DEPLOY_DIGITALOCEAN.md](docs/DEPLOY_DIGITALOCEAN.md) |

> Hosts with a temporary disk (e.g. Render's free plan) lose a SQLite database on every restart or redeploy.
> Use a host with persistent storage (PythonAnywhere, a VPS) for SQLite.

Moving data from SQLite to PostgreSQL later takes 3 commands:

```bash
python manage.py export_data export.json    # on the SQLite setup
# on the PostgreSQL setup (empty database):
python manage.py migrate
python manage.py loaddata export.json
```

---

## 10. Developing without Docker

Requires Python 3.10–3.13 (3.12 recommended). No database server is needed: SQLite is used automatically.

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
set DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py test
```

---

## 11. Future roadmap

| Item | Notes |
|---|---|
| **Excel import - more formats** | V1 imports cases (+ first payment) from .xlsx. Next: separate payment-only uploads and doctor-specific column mappings once their real files are available. |
| **REST API** | Django REST Framework endpoints on top of the existing querysets and services, for a native iOS/Android app. |
| **WhatsApp reminders** | WhatsApp Business API templates triggered from the existing reminder engine. |
| **Statements** | A PDF/Excel statement of pending cases per hospital, to send with follow-ups. |
