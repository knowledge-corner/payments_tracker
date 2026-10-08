# User manual (docs/Payments_Tracker_User_Manual.pdf)

Rebuild after UI changes (needs Node + Playwright with Chromium, Python with Pillow, openpyxl):

1. Fresh demo database with sample data (fake names only):
   `DATA_DIR=/tmp/manual DJANGO_DEBUG=1 python manage.py migrate && DATA_DIR=/tmp/manual python manage.py shell < docs/manual/seed.py`
2. Run the app on port 8130: `DATA_DIR=/tmp/manual DJANGO_DEBUG=1 python manage.py runserver 127.0.0.1:8130`
3. In a working folder, create `bad_upload.xlsx` (see the bulk-upload step) and run `node shots.js` (phone-size screenshots).
4. Resize screenshots into `img/` (600 px wide JPEG), then `python build.py` and `node print.js`.

`build.py` holds all manual text - edit it there.
# Rebuild note: before running shots.js, run `python manage.py send_notifications` once so the
# Notification settings screenshot shows "Reminder sender is running".
