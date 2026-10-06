"""Send due push notifications. Run hourly (Docker does this automatically) or once a day."""
from django.core.management.base import BaseCommand

from notifications.services import run_scheduled


class Command(BaseCommand):
    help = "Send scheduled push notifications (payment reminders, morning summary, weekly report)."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        result = run_scheduled()
        if not options["quiet"] or result["sent"]:
            self.stdout.write(f"Notifications: {result['sent']} sent to {result['users']} subscribed user(s).")
