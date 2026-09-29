from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.testing import make_case, make_doctor, make_hospital
from payments.models import Payment


class ReportTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.a = make_hospital("Alpha", fee=1000)
        self.b = make_hospital("Beta", fee=2000)
        case = make_case(self.doctor, self.a, fee=1000)
        Payment.objects.create(case=case, amount=Decimal("400"), mode="upi")
        make_case(self.doctor, self.b, fee=2000)
        self.client.force_login(self.doctor.user)

    def test_monthly(self):
        ctx = self.client.get(reverse("reports:monthly")).context
        self.assertEqual(ctx["totals"]["billed"], Decimal("3000"))
        self.assertEqual(ctx["totals"]["received"], Decimal("400"))
        self.assertEqual(ctx["totals"]["outstanding"], Decimal("2600"))
        self.assertEqual(len(ctx["rows"]), 12)

    def test_hospital_wise_sorted_by_outstanding(self):
        rows = self.client.get(reverse("reports:hospitals")).context["rows"]
        self.assertEqual([r["hospital"].name for r in rows], ["Beta", "Alpha"])
        self.assertEqual(rows[1]["outstanding"], Decimal("600"))

    def test_payment_history_and_csv(self):
        ctx = self.client.get(reverse("reports:payments") + "?mode=upi").context
        self.assertEqual(ctx["summary"]["total"], Decimal("400"))
        response = self.client.get(reverse("reports:payments") + "?export=csv")
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("Alpha", response.content.decode())
