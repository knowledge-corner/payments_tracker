"""Builds pricing.html (printed to Team_Anesthesia_Running_Costs.pdf by print_pricing.js).

Edit the numbers in PRICES / ASSUMPTIONS below and rebuild:
    python build_pricing.py && node print_pricing.js
"""
import base64
import pathlib

HERE = pathlib.Path(__file__).parent
USD_INR = 88.0          # exchange rate used for all conversions
GST = 0.18              # GST that DigitalOcean adds on Indian accounts
USERS = 10

DROPLET_USD = 6.00                      # Basic, 1 vCPU, 1 GB RAM, 25 GB SSD, 1000 GB transfer
BACKUP_RATE_USD = 0.04                  # usage-based weekly backups, per GiB per month
BACKUP_GIB = 5                          # space used on the server (OS + app + data)
BACKUP_LOW, BACKUP_HIGH = BACKUP_RATE_USD * BACKUP_GIB, BACKUP_RATE_USD * BACKUP_GIB * 4
BACKUP_TYPICAL = 0.50
DOMAIN_Y1, DOMAIN_RENEWAL = 499, 749     # teamanaesthesia.co.in (GoDaddy, as quoted)


def inr(x):
    return "₹{:,.0f}".format(round(x))


def usd(x):
    return "${:,.2f}".format(x)


def do_year(backup_usd_month):
    base = (DROPLET_USD + backup_usd_month) * 12 * USD_INR
    return base, base * GST, base * (1 + GST)


typ_base, typ_gst, typ_total = do_year(BACKUP_TYPICAL)
low_total = do_year(BACKUP_LOW)[2]
high_total = do_year(BACKUP_HIGH)[2]
y1, y2 = typ_total + DOMAIN_Y1, typ_total + DOMAIN_RENEWAL

LOGO = "data:image/png;base64," + base64.b64encode((HERE.parent / "manual" / "logo.png").read_bytes()).decode()

summary_rows = [
    ("Server (DigitalOcean Droplet)", f"{usd(DROPLET_USD)} / month", inr(DROPLET_USD * USD_INR * 12), inr(DROPLET_USD * USD_INR * 12)),
    ("Weekly server backups (usage-based, typical)", f"≈ {usd(BACKUP_TYPICAL)} / month", inr(BACKUP_TYPICAL * USD_INR * 12), inr(BACKUP_TYPICAL * USD_INR * 12)),
    ("GST 18% on DigitalOcean", "", inr(typ_gst), inr(typ_gst)),
    ("Domain teamanaesthesia.co.in", "per year", inr(DOMAIN_Y1), inr(DOMAIN_RENEWAL)),
]

html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Team Anesthesia - Running Costs</title><style>
@page {{ size: A4; margin: 16mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Noto Sans','DejaVu Sans',Arial,sans-serif; color:#1f2937; font-size:10.5pt; line-height:1.45; margin:0; }}
.head {{ display:flex; align-items:center; gap:16px; padding-bottom:12px; border-bottom:3px solid #f5b83d; margin-bottom:14px; }}
.head img {{ width:58px; height:58px; border-radius:14px; }}
.head h1 {{ margin:0; color:#2e2a6e; font-size:21pt; }}
.head .sub {{ color:#555; font-size:11pt; }}
h2 {{ color:#2e2a6e; font-size:13pt; margin:18px 0 6px; }}
table {{ width:100%; border-collapse:collapse; font-size:10pt; margin:4px 0 6px; }}
th {{ background:#2e2a6e; color:#fff; text-align:left; padding:6px 8px; font-weight:600; }}
td {{ padding:6px 8px; border-bottom:1px solid #e5e7eb; vertical-align:top; }}
tr:nth-child(even) td {{ background:#f8f9fc; }}
td.num, th.num {{ text-align:right; white-space:nowrap; }}
tr.total td {{ font-weight:700; background:#eef0fb !important; border-top:2px solid #2e2a6e; }}
.kpis {{ display:flex; gap:10px; margin:6px 0 4px; }}
.kpi {{ flex:1; border:1px solid #e3e5ee; border-radius:10px; padding:10px 12px; background:#fafbff; }}
.kpi .v {{ font-size:17pt; font-weight:700; color:#2e2a6e; }}
.kpi .l {{ font-size:9pt; color:#666; }}
.note {{ background:#fff7e6; border-left:4px solid #f5b83d; padding:7px 10px; border-radius:6px; font-size:9.5pt; margin:8px 0; }}
.tip {{ background:#ecfdf3; border-left:4px solid #2f9e62; padding:7px 10px; border-radius:6px; font-size:9.5pt; margin:8px 0; }}
ul {{ margin:4px 0; padding-left:18px; }} li {{ margin-bottom:3px; }}
.small {{ font-size:9pt; color:#666; }}
.avoid {{ break-inside: avoid; }}
</style></head><body>

<div class='head'><img src='{LOGO}' alt=''><div><h1>Team Anesthesia - Running Costs</h1>
<div class='sub'>Hosting, backups and domain · for up to {USERS} users · October 2026</div></div></div>

<div class='kpis'>
  <div class='kpi'><div class='v'>{inr(y1)}</div><div class='l'>Year 1 total (incl. GST)</div></div>
  <div class='kpi'><div class='v'>{inr(y2)}</div><div class='l'>Year 2 onwards, per year</div></div>
  <div class='kpi'><div class='v'>{inr(y2 / 12)}</div><div class='l'>Per month (year 2+)</div></div>
  <div class='kpi'><div class='v'>{inr(y2 / 12 / USERS)}</div><div class='l'>Per user per month ({USERS} users)</div></div>
</div>

<h2>1. Annual cost summary</h2>
<table>
<thead><tr><th>Item</th><th>Billed as</th><th class='num'>Year 1</th><th class='num'>Year 2 onwards</th></tr></thead>
<tbody>
{''.join(f"<tr><td>{a}</td><td>{b}</td><td class='num'>{c}</td><td class='num'>{d}</td></tr>" for a, b, c, d in summary_rows)}
<tr class='total'><td>Total per year</td><td></td><td class='num'>{inr(y1)}</td><td class='num'>{inr(y2)}</td></tr>
<tr><td>Equivalent per month</td><td></td><td class='num'>{inr(y1 / 12)}</td><td class='num'>{inr(y2 / 12)}</td></tr>
</tbody></table>
<div class='small'>Range depending on backup size: Year 1 {inr(low_total + DOMAIN_Y1)} - {inr(high_total + DOMAIN_Y1)};
Year 2+ {inr(low_total + DOMAIN_RENEWAL)} - {inr(high_total + DOMAIN_RENEWAL)}.</div>

<h2>2. DigitalOcean - what is included</h2>
<table class='avoid'>
<thead><tr><th>Component</th><th>Specification</th><th class='num'>Price</th></tr></thead>
<tbody>
<tr><td>Droplet (server)</td><td>Basic · Regular · 1 vCPU · 1 GB RAM · 25 GB SSD · Bangalore (BLR1)</td><td class='num'>{usd(DROPLET_USD)}/month ({inr(DROPLET_USD * USD_INR)})</td></tr>
<tr><td>Data transfer</td><td>1,000 GB/month included (the app uses well under 5 GB)</td><td class='num'>Included</td></tr>
<tr><td>Weekly backups</td><td>Usage-based · weekly · 4 weeks kept · Sunday 6-10 am IST · {usd(BACKUP_RATE_USD)} per GiB-month on ≈{BACKUP_GIB} GiB used</td><td class='num'>{usd(BACKUP_LOW)} - {usd(BACKUP_HIGH)}/month</td></tr>
<tr><td>Database, HTTPS certificate, security updates, nightly database copy</td><td>Run on the same server (PostgreSQL, Caddy + Let's Encrypt, automatic updates, firewall)</td><td class='num'>Included</td></tr>
<tr><td>GST</td><td>18% added by DigitalOcean on Indian accounts</td><td class='num'>{inr(typ_gst)}/year</td></tr>
</tbody></table>
<div class='note'><b>Backups:</b> DigitalOcean charges only for the space the server actually uses (about {BACKUP_GIB} GiB:
operating system, app and data). The app's own data for {USERS} users grows by less than 0.1 GiB a year, so this cost stays
almost flat. The older fixed backup plan would cost {usd(DROPLET_USD * 0.2)}/month.</div>

<h2>3. Domain</h2>
<table class='avoid'>
<thead><tr><th>Domain</th><th>Registrar</th><th class='num'>Year 1</th><th class='num'>Renewal (per year)</th></tr></thead>
<tbody><tr><td>teamanaesthesia.co.in</td><td>GoDaddy</td><td class='num'>{inr(DOMAIN_Y1)}</td><td class='num'>{inr(DOMAIN_RENEWAL)}</td></tr></tbody></table>
<div class='tip'>Turn on <b>auto-renew</b> at GoDaddy so the domain never lapses. The app runs at
<b>https://teamanaesthesia.co.in</b> (www.teamanaesthesia.co.in redirects there).</div>

<h2>4. What costs nothing extra</h2>
<ul>
<li>The Team Anesthesia app itself (own code, no per-user licence fees).</li>
<li>HTTPS certificate (Let's Encrypt, renewed automatically).</li>
<li>Push notifications / reminders on phones (sent by the server, no SMS or WhatsApp charges).</li>
<li>Nightly database backup kept on the server for 14 days.</li>
<li>Adding more users - no per-user charges.</li>
</ul>

<h2>5. When costs could change</h2>
<table class='avoid'>
<thead><tr><th>Situation</th><th>Action</th><th class='num'>New server price</th></tr></thead>
<tbody>
<tr><td>More than ~25 regular users, or the app feels slow</td><td>Resize the Droplet to 2 GB RAM (one click, no reinstall)</td><td class='num'>$12/month ({inr(12 * USD_INR)})</td></tr>
<tr><td>Daily instead of weekly server backups</td><td>Change backup frequency in DigitalOcean (see its price estimate before saving)</td><td class='num'>Shown by DigitalOcean</td></tr>
<tr><td>Exchange rate moves</td><td>DigitalOcean bills in US$; every ₹1 change in the rate changes the yearly cost by about {inr((DROPLET_USD + BACKUP_TYPICAL) * 12 * (1 + GST))}</td><td class='num'>-</td></tr>
</tbody></table>

<h2>6. Payment notes</h2>
<ul>
<li>DigitalOcean bills <b>monthly</b>, in US$, to the card on the account. The bank may add a small foreign-transaction fee (typically 1-3.5%).</li>
<li>Domain is paid <b>yearly</b> to GoDaddy.</li>
<li>Assumptions: ₹{USD_INR:.0f} per US$; GST 18% on DigitalOcean; domain prices as quoted by GoDaddy. Prices as of October 2026 - check the
DigitalOcean billing page and GoDaddy renewal notice for exact amounts.</li>
</ul>
</body></html>"""
(HERE / "pricing.html").write_text(html, encoding="utf-8")
print("Year 1", inr(y1), "| Year 2+", inr(y2), "| per month", inr(y2 / 12), "| per user/month", inr(y2 / 12 / USERS))
