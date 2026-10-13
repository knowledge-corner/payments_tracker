"""Set or show the practice code (the developer's way to reset it from the server console).

    python manage.py set_practice_code 482913
    python manage.py set_practice_code --show
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import AppSettings


class Command(BaseCommand):
    help = "Set (or --show) the practice code everyone enters once per phone."

    def add_arguments(self, parser):
        parser.add_argument("code", nargs="?")
        parser.add_argument("--show", action="store_true")

    def handle(self, *args, code=None, show=False, **options):
        settings_obj = AppSettings.load()
        if show or not code:
            self.stdout.write(f"Practice code: {settings_obj.practice_code or '(not set)'}")
            return
        code = code.strip()
        if len(code) < 4 or " " in code or len(code) > 30:
            raise CommandError("Use at least 4 letters or digits, no spaces.")
        settings_obj.practice_code = code
        settings_obj.save(update_fields=["practice_code", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Practice code set to {code}. All phones will ask for it."))
