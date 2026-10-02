"""
Wipe all business data for a clean start - KEEPS user logins and doctor profiles.

    python manage.py reset_app_data --yes

Deletes: cases, payments, follow-ups, contacts, hospitals, notification history.
Keeps:   users (admin + doctors), doctor profiles, app settings, departments,
         notification preferences / subscribed devices.
Then reloads the starter hospital list.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all cases/payments/hospitals/contacts (users are kept) and reload the starter hospital list."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirm deletion.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not opts["yes"]:
            raise CommandError("This deletes all cases, payments, contacts and hospitals. Re-run with --yes to confirm.")
        from accounts.models import User
        from cases.models import Case
        from contacts.models import Contact, ContactAffiliation, Surgeon, SurgeonHospital
        from hospitals.directory import load_starter
        from hospitals.models import Hospital
        from notifications.models import NotifiedCase, SentNotification
        from payments.models import Payment, PaymentFollowUp

        users_before = User.objects.count()
        counts = {}
        for label, model in [
            ("notifications", SentNotification), ("notification marks", NotifiedCase),
            ("follow-ups", PaymentFollowUp), ("payments", Payment), ("cases", Case),
            ("contact links", ContactAffiliation), ("contacts", Contact),
            ("surgeon links", SurgeonHospital), ("surgeons", Surgeon),
        ]:
            counts[label] = model.objects.all().delete()[0]
        Hospital.objects.update(merged_into=None)
        counts["hospitals"] = Hospital.objects.all().delete()[0]
        added = load_starter()
        assert User.objects.count() == users_before
        summary = ", ".join(f"{n} {label}" for label, n in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Deleted: {summary}."))
        self.stdout.write(f"Users kept: {users_before}. Starter hospitals loaded: {added}.")
