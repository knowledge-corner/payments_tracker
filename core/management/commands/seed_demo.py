"""
Load realistic dummy data for development and demos.

    python manage.py seed_demo            # only if the database has no cases yet
    python manage.py seed_demo --reset    # wipe cases/payments/hospitals and reload
"""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Doctor, User
from cases.models import Case
from core.models import AppSettings
from hospitals.models import Hospital
from payments.models import Payment, PaymentFollowUp

DEMO_PASSWORD = "Demo@12345"

HOSPITALS = [
    # name, city, contact person, phone, default fee, payment terms (None = global)
    ("Sahyadri Speciality Hospital", "Pune", "Mr. Rahul Joshi (Billing)", "+91 98220 11223", 6000, 45),
    ("Ruby Hall Clinic", "Pune", "Ms. Neha Kulkarni", "+91 98230 44556", 7500, 60),
    ("Deenanath Mangeshkar Hospital", "Pune", "Mr. Sanjay Patil", "+91 98900 77881", 7000, None),
    ("Jupiter Hospital", "Pune", "Ms. Priya Nair", "+91 97640 22334", 8000, 45),
    ("Sunshine Maternity Home", "Pune", "Dr. Kavita Shah", "+91 98221 55667", 4500, 15),
    ("Lifeline Day Surgery Centre", "Pune", "Mr. Amit Deshmukh", "+91 90110 88990", 3500, None),
    ("Shree Ortho & Trauma Centre", "Pimpri", "Mr. Vikas More", "+91 98505 33445", 5500, None),
    ("City Eye & ENT Hospital", "Pune", "Ms. Sneha Pawar", "+91 98811 66778", 3000, 30),
]

PROCEDURES = [
    ("LSCS - spinal", 1.0),
    ("General anaesthesia (GA)", 1.2),
    ("Spinal anaesthesia", 0.9),
    ("Laparoscopic cholecystectomy - GA", 1.3),
    ("Total knee replacement - CSE", 1.5),
    ("Peripheral nerve block", 0.7),
    ("Endoscopy sedation", 0.5),
    ("Labour analgesia", 0.8),
    ("Cataract - MAC", 0.5),
    ("Emergency laparotomy - GA", 1.4),
]

DOCTORS = [
    ("dr.mehta", "Dr. Anjali Mehta", "anjali.mehta@example.com", "+91 98220 10001", "MMC-2009/04512"),
    ("dr.rao", "Dr. Vikram Rao", "vikram.rao@example.com", "+91 98220 10002", "MMC-2012/07788"),
]


class Command(BaseCommand):
    help = "Create demo admin, doctors, hospitals, cases, payments and follow-ups."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing cases/hospitals first.")
        parser.add_argument("--months", type=int, default=7, help="How many months of history to generate.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            PaymentFollowUp.objects.all().delete()
            Payment.objects.all().delete()
            Case.objects.all().delete()
            Hospital.objects.all().delete()
        elif Case.objects.exists():
            self.stdout.write("Demo data skipped: cases already exist (use --reset to reload).")
            return

        rng = random.Random(42)
        today = timezone.localdate()
        AppSettings.load()

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"role": User.ROLE_ADMIN, "is_staff": True, "is_superuser": True,
                      "first_name": "Clinic", "last_name": "Admin", "email": "admin@example.com"},
        )
        if created:
            admin.set_password("Admin@12345")
            admin.save()

        doctors = []
        for username, name, email, phone, reg in DOCTORS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"role": User.ROLE_DOCTOR, "email": email},
            )
            if created:
                first, _, last = name.replace("Dr. ", "").partition(" ")
                user.first_name, user.last_name = first, last
                user.set_password(DEMO_PASSWORD)
                user.save()
            doctor, _ = Doctor.objects.get_or_create(
                user=user, defaults={"display_name": name, "phone": phone, "registration_no": reg},
            )
            doctors.append(doctor)

        hospitals = []
        for name, city, contact, phone, fee, terms in HOSPITALS:
            hospital, _ = Hospital.objects.get_or_create(
                name=name,
                defaults={"city": city, "address": f"{city}, Maharashtra", "contact_person": contact,
                          "contact_number": phone, "default_fee": Decimal(fee), "payment_terms_days": terms},
            )
            hospitals.append(hospital)

        # Each doctor works mostly at 4-5 "home" hospitals.
        case_count = payment_count = followup_count = 0
        start = today - datetime.timedelta(days=30 * opts["months"])
        for doctor in doctors:
            home = rng.sample(hospitals, 5)
            day = start
            while day <= today:
                for _ in range(rng.choices([0, 1, 2, 3], weights=[35, 35, 22, 8])[0]):
                    hospital = rng.choice(home)
                    proc, factor = rng.choice(PROCEDURES)
                    fee = Decimal(round(float(hospital.default_fee) * factor / 500) * 500 or 500)
                    case = Case.objects.create(
                        doctor=doctor, hospital=hospital, case_date=day, fee=fee,
                        procedure_type=proc, patient_reference=f"IP-{rng.randint(10000, 99999)}",
                        created_by=doctor.user,
                    )
                    case_count += 1
                    payment_count += self._payments(case, rng, today)
                    followup_count += self._followups(case, rng, today)
                day += datetime.timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded: {len(doctors)} doctors, {len(hospitals)} hospitals, "
            f"{case_count} cases, {payment_count} payments, {followup_count} follow-ups."
        ))
        self.stdout.write("Logins -> admin / Admin@12345   dr.mehta / Demo@12345   dr.rao / Demo@12345")

    def _payments(self, case, rng, today):
        age = (today - case.case_date).days
        if age < 5:
            return 0
        roll = rng.random()
        # Older cases are more likely to be settled.
        paid_prob = min(0.85, 0.25 + age / 150)
        if roll < paid_prob:
            parts = [case.fee]
        elif roll < paid_prob + 0.15:
            first = (case.fee * Decimal(rng.choice(["0.4", "0.5", "0.6"]))).quantize(Decimal("1"))
            parts = [first]
        else:
            return 0
        if len(parts) == 1 and parts[0] == case.fee and rng.random() < 0.2:
            half = (case.fee / 2).quantize(Decimal("1"))
            parts = [half, case.fee - half]
        pay_day = case.case_date
        for amount in parts:
            pay_day = min(today, pay_day + datetime.timedelta(days=rng.randint(10, 50)))
            Payment.objects.create(
                case=case, amount=amount, payment_date=pay_day,
                mode=rng.choice(["bank", "bank", "upi", "upi", "cheque", "cash"]),
                reference_no=f"TXN{rng.randint(100000, 999999)}",
                created_by=case.doctor.user,
            )
        return len(parts)

    def _followups(self, case, rng, today):
        paid = sum(p.amount for p in case.payments.all())
        age = (today - case.case_date).days
        if paid >= case.fee or age < 10 or rng.random() < 0.45:
            return 0
        n = rng.randint(1, 2 if age < 40 else 3)
        for i in range(n):
            day = case.case_date + datetime.timedelta(days=min(age, 8 + i * 9 + rng.randint(0, 3)))
            PaymentFollowUp.objects.create(
                case=case, followup_date=min(day, today),
                method=rng.choice(["call", "call", "whatsapp", "email", "in_person"]),
                contact_person=case.hospital.contact_person,
                notes=rng.choice([
                    "Billing said cheque is under process.",
                    "Asked to resend case list for the month.",
                    "Payment approved, will be released next week.",
                    "Accounts person on leave, call again.",
                    "Promised NEFT by month end.",
                ]),
                created_by=case.doctor.user,
            )
        return n
