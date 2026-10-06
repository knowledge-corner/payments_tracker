"""Explain, for each user, whether notifications can reach them and what is due.

    python manage.py check_notifications              # everyone with the app installed
    python manage.py check_notifications dr.anjali    # one user
    python manage.py check_notifications dr.anjali --send-test
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from notifications.models import NotificationKind, NotificationPreference, PushSubscription, SentNotification
from notifications.push import notify
from payments.services import receivables_for


class Command(BaseCommand):
    help = "Diagnose push notifications: devices, settings, reminders due today, recent sends."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?")
        parser.add_argument("--send-test", action="store_true", help="Also send a test notification now.")

    def handle(self, *args, username=None, send_test=False, **options):
        now = timezone.localtime()
        self.stdout.write(f"Server time: {now:%d %b %Y %H:%M} ({settings.TIME_ZONE})")
        if username:
            users = User.objects.filter(username__iexact=username)
            if not users:
                raise CommandError(f"No user '{username}'.")
        else:
            users = User.objects.filter(pk__in=PushSubscription.objects.values("user_id")).order_by("username")
            if not users:
                self.stdout.write(self.style.WARNING(
                    "No user has turned on notifications on any device yet "
                    "(app > profile menu > Notification settings > Turn on)."))
                return
        for user in users:
            self.check_user(user, now, send_test)

    def check_user(self, user, now, send_test):
        w = self.stdout.write
        w("")
        w(self.style.MIGRATE_HEADING(f"== {user.username} =="))
        devices = list(PushSubscription.objects.filter(user=user))
        prefs = NotificationPreference.for_user(user)
        problems = []
        w(f"Devices turned on: {len(devices)}")
        for d in devices:
            last = timezone.localtime(d.last_success_at).strftime("%d %b %H:%M") if d.last_success_at else "never"
            w(f"  - {d.device or 'device'} | last delivered: {last} | failures: {d.failure_count}")
        if not devices:
            problems.append("No device: open the app on the phone > Notification settings > Turn on.")
        if not prefs.push_enabled:
            problems.append("'All push notifications' is switched off in Notification settings.")
        kinds = ", ".join(label for kind, label, _ in NotificationKind.CHOICES if getattr(prefs, kind, False)) or "none"
        w(f"Notification time: {prefs.summary_hour}:00 | switched on: {kinds}")
        if now.hour < prefs.summary_hour:
            w(f"(It is before {prefs.summary_hour}:00 now, so nothing is sent yet today.)")

        cases = receivables_for(user, now.date())
        due = [c for c in cases if c.reminder.due]
        w(f"Unpaid cases: {len(cases)} | payment reminders due today: {len(due)}")
        for c in due[:10]:
            w(f"  - {c.hospital.name} · case {c.case_date:%d %b} · reminder date {c.reminder.last_trigger:%d %b %Y}")
        upcoming = sorted((c.reminder.next_trigger, c) for c in cases if c.reminder.next_trigger)
        for when, c in upcoming[:5]:
            w(f"  next: {when:%d %b %Y} - {c.hospital.name} (case {c.case_date:%d %b})")

        recent = SentNotification.objects.filter(user=user)[:5]
        w("Recently sent:" if recent else "Recently sent: nothing yet")
        for n in recent:
            w(f"  - {timezone.localtime(n.created_at):%d %b %H:%M} | {n.title} | {n.devices} device(s)")

        if send_test:
            sent = notify(user, NotificationKind.TEST, "Test notification", "Notifications are working on this device.",
                          url="/notifications/")
            (w(self.style.SUCCESS(f"Test sent to {sent} device(s).")) if sent
             else problems.append("Test could not be delivered (see devices above / server log)."))
        for p in problems:
            w(self.style.WARNING("PROBLEM: " + p))
        if not problems:
            w(self.style.SUCCESS("OK - this user can receive notifications."))
