# Production deployment (DigitalOcean or any Ubuntu server)

One command sets up the app with **PostgreSQL**, **automatic HTTPS**, a **firewall**, **daily backups**
and a `payments` helper command. Plan about 20 minutes (most of it waiting).

| Item | Recommendation | Approx. cost |
|---|---|---|
| Server | DigitalOcean Droplet, **Ubuntu 24.04**, Basic 1 GB / 1 vCPU, region **Bangalore (BLR1)** | $6 / month |
| Server backups | Enable "Backups" when creating the Droplet (weekly snapshot) | +$1.20 / month |
| Database | PostgreSQL 16 in Docker on the same server | included |
| HTTPS | Caddy + Let's Encrypt (automatic, renews itself) | free |
| Domain | e.g. `payments.yourpractice.in` | ~₹500-900 / year |

> Any Ubuntu 22.04/24.04 server works the same way (AWS Lightsail Mumbai, Hetzner, ...).

---

## Step 1 - Create the server

1. DigitalOcean → **Create → Droplets**.
2. Region **Bangalore**, image **Ubuntu 24.04 (LTS) x64**, size **Basic → Regular → $6/mo (1 GB)**.
3. Authentication: **SSH key** (recommended) or a strong root password.
4. Tick **Enable automated backups**. Create the Droplet and note its **IP address**.

## Step 2 - Point your domain to the server

At your domain registrar (GoDaddy, Hostinger, Namecheap, ...) add a DNS record:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `payments` (for payments.yourdomain.in) | the Droplet IP | 600 / default |

DNS usually updates within 5-30 minutes. HTTPS works once it has.

## Step 3 - Run the setup script

Connect to the server (Windows: open **Command Prompt / PowerShell**):

```bash
ssh root@<droplet IP>
```

Then run:

```bash
curl -fsSL https://raw.githubusercontent.com/knowledge-corner/payments_tracker/main/deploy/setup_server.sh -o setup.sh
bash setup.sh
```

It asks for:

| Question | Example |
|---|---|
| Domain for the app | `payments.yourpractice.in` |
| Admin username | `admin` |
| Admin email | `you@yourpractice.in` |
| Admin password | at least 10 characters (typed twice, not shown) |
| Hospital directory CSV link | optional - a data.gov.in download link, or press Enter and upload the CSV later in the app |

Everything else (database password, secret key) is generated automatically and stored in
`/opt/payments_tracker/.env` (readable by root only).

When it prints **Done!**, open `https://payments.yourpractice.in` and sign in with the admin login.

## Step 4 - First things in the app

1. **Settings** → decide on *Allow new doctors to sign up* and *New sign-ups need admin approval*
   (recommended for real use: approval **on**).
2. **Doctors** → add doctors (or let them sign up); **Hospitals** → add hospitals, or import cases from Excel.
3. Phones: open the address → *Add to Home Screen* (iPhone) / *Install app* (Android).

---

## Everyday commands (on the server)

| Command | What it does |
|---|---|
| `payments update` | Download the latest version, rebuild, apply database migrations |
| `payments status` | Show running containers |
| `payments logs` | Live application log (Ctrl+C to stop) |
| `payments backup` | Back up the database now |
| `payments restore /var/backups/payments_tracker/db_....sql.gz` | Restore a backup (asks for confirmation) |
| `payments createadmin` | Create another admin login |

## "Forgot password"

No email setup is needed: on **Forgot password?** the doctor enters their username, registered
mobile number and registered email. If all three match, they set a new password on the spot
(5 wrong attempts lock the form for 15 minutes). Admin logins without a doctor profile reset with
`python manage.py changepassword <username>`.

## Backups

- **Daily at 02:30** a compressed PostgreSQL dump is saved to `/var/backups/payments_tracker/` (last 14 days kept).
- **Weekly** Droplet snapshot (if enabled in Step 1).
- **Recommended - off-server copy** (protects against losing the server):
  ```bash
  rclone config                      # e.g. add Google Drive, name it "gdrive"
  nano /etc/payments-backup.conf     # set RCLONE_REMOTE="gdrive:payments-backups"
  payments backup                    # test: should say "Copied off-server"
  ```
- Test a restore once before go-live (`payments restore <file>`).

## What the script sets up

| Area | Details |
|---|---|
| Security | Firewall (only SSH/80/443 open), fail2ban against SSH password guessing, automatic security updates, HTTPS with HSTS, secure cookies |
| Stability | 2 GB swap (safe on a 1 GB server), containers restart automatically after a reboot |
| App | Docker: app (gunicorn), PostgreSQL 16, Caddy; migrations run automatically on every start/update |
| Time zone | Asia/Kolkata |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser shows a certificate / "not secure" error | DNS not updated yet - wait, then `payments restart` |
| "Bad Request (400)" | The address typed in the browser differs from the domain given to the script - check `APP_DOMAIN` / `DJANGO_ALLOWED_HOSTS` in `/opt/payments_tracker/.env`, then `payments update` |
| App not loading | `payments status` and `payments logs` |
| Change the domain later | Edit `APP_DOMAIN`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` in `.env`, then `payments update` |
| Server feels slow with many doctors | Resize the Droplet to 2 GB in the DigitalOcean panel (no reinstall needed) |

---

## Optional: bring data from the SQLite test site

Not needed for a fresh start. If you ever want the test data: on the old site run
`python manage.py export_data export.json`, copy the file to the server, then

```bash
cd /opt/payments_tracker
docker compose -f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.prod.yml cp export.json web:/app/data/import.json
docker compose -f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.prod.yml exec web python manage.py loaddata /app/data/import.json
```
(Do this on a new, empty installation.)
