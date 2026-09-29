"""
Export all app data to a JSON file, e.g. to move from SQLite (client testing)
to PostgreSQL (production):

    python manage.py export_data backup.json          # on the old (SQLite) setup
    # point DATABASE_URL at PostgreSQL, then:
    python manage.py migrate
    python manage.py loaddata backup.json
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export users, doctors, hospitals, cases, payments, follow-ups and settings to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("output", nargs="?", default="payments_tracker_export.json")

    def handle(self, *args, **options):
        call_command(
            "dumpdata",
            natural_foreign=True,
            natural_primary=True,
            exclude=["contenttypes", "auth.permission", "admin.logentry", "sessions"],
            indent=1,
            output=options["output"],
        )
        self.stdout.write(self.style.SUCCESS(f"Exported to {options['output']}"))
