import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AppSettings
from core.testing import make_admin, make_case, make_doctor, make_hospital
from payments.models import Payment

from .models import Case, PaymentStatus, compute_status


class CaseStatusTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.hospital = make_hospital(terms=30)

    def status_of(self, case):
        return Case.objects.with_totals().get(pk=case.pk)

    def test_due_date_uses_hospital_terms(self):
        case = make_case(self.doctor, self.hospital, days_ago=0)
        self.assertEqual(case.due_date, case.case_date + datetime.timedelta(days=30))

    def test_due_date_falls_back_to_global_setting(self):
        settings = AppSettings.load()
        settings.default_payment_terms_days = 45
        settings.save()
        hospital = make_hospital(name="No terms", terms=None)
        case = make_case(self.doctor, hospital)
        self.assertEqual(case.due_date, case.case_date + datetime.timedelta(days=45))

    def test_pending_partial_paid_overdue(self):
        case = make_case(self.doctor, self.hospital, days_ago=5, fee=5000)
        self.assertEqual(self.status_of(case).status, PaymentStatus.PENDING)

        Payment.objects.create(case=case, amount=Decimal("2000"))
        annotated = self.status_of(case)
        self.assertEqual(annotated.status, PaymentStatus.PARTIAL)
        self.assertEqual(annotated.outstanding, Decimal("3000"))

        Payment.objects.create(case=case, amount=Decimal("3000"))
        self.assertEqual(self.status_of(case).status, PaymentStatus.PAID)
        self.assertEqual(self.status_of(case).outstanding, Decimal("0"))

        old = make_case(self.doctor, self.hospital, days_ago=40, fee=5000)
        Payment.objects.create(case=old, amount=Decimal("1000"))
        self.assertEqual(self.status_of(old).status, PaymentStatus.OVERDUE)

    def test_python_and_sql_status_agree(self):
        case = make_case(self.doctor, self.hospital, days_ago=40, fee=5000)
        Payment.objects.create(case=case, amount=Decimal("500"))
        fresh = Case.objects.get(pk=case.pk)
        self.assertEqual(fresh.payment_status, self.status_of(case).status)
        self.assertEqual(
            compute_status(Decimal("100"), Decimal("100"), timezone.localdate() - datetime.timedelta(days=1)),
            PaymentStatus.PAID,
        )


class CaseViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.other = make_doctor("dr.other", "Dr. Other")
        self.hospital = make_hospital(fee=6500)
        self.client.force_login(self.doctor.user)

    def test_add_case_prefills_hospital_fee(self):
        self.client.force_login(self.doctor.user)
        response = self.client.get(reverse("cases:add") + f"?hospital={self.hospital.pk}")
        self.assertContains(response, 'data-fee="6500"')
        self.assertEqual(response.context["form"].initial["fee"], 6500)

    def test_add_case_with_custom_fee_and_payment(self):
        response = self.client.post(reverse("cases:add"), {
            "hospital": self.hospital.pk, "case_date": timezone.localdate().isoformat(),
            "fee": "7000", "procedure_type": "Spinal", "paid_now": "on", "paid_amount": "7000", "paid_mode": "upi",
        })
        self.assertRedirects(response, reverse("dashboard:home"))
        case = Case.objects.get()
        self.assertEqual(case.doctor, self.doctor)
        self.assertEqual(case.fee, Decimal("7000"))
        self.assertEqual(case.payment_status, PaymentStatus.PAID)

    def test_future_case_date_rejected(self):
        response = self.client.post(reverse("cases:add"), {
            "hospital": self.hospital.pk, "fee": "100",
            "case_date": (timezone.localdate() + datetime.timedelta(days=2)).isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Case.objects.exists())

    def test_doctor_cannot_see_other_doctors_case(self):
        case = make_case(self.other, self.hospital)
        self.assertEqual(self.client.get(reverse("cases:detail", args=[case.pk])).status_code, 403)
        listing = self.client.get(reverse("cases:list"))
        self.assertEqual(listing.context["page"].paginator.count, 0)

    def test_admin_sees_all_and_can_filter_by_doctor(self):
        make_case(self.doctor, self.hospital)
        make_case(self.other, self.hospital)
        self.client.force_login(make_admin())
        self.assertEqual(self.client.get(reverse("cases:list")).context["page"].paginator.count, 2)
        filtered = self.client.get(reverse("cases:list") + f"?doctor={self.other.pk}")
        self.assertEqual(filtered.context["page"].paginator.count, 1)
