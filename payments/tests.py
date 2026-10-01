import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cases.models import Case
from core.models import AppSettings
from core.testing import make_case, make_doctor, make_hospital

from .models import Payment, PaymentFollowUp
from .services import receivables_for, reminder_state


class PaymentViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.hospital = make_hospital()
        self.case = make_case(self.doctor, self.hospital, days_ago=3, fee=5000)
        self.client.force_login(self.doctor.user)

    def test_partial_payments(self):
        url = reverse("payments:record_for_case", args=[self.case.pk])
        for amount in ("2000", "1500"):
            self.client.post(url, {"amount": amount, "payment_date": timezone.localdate().isoformat(), "mode": "upi"})
        case = Case.objects.with_totals().get(pk=self.case.pk)
        self.assertEqual(case.total_paid, Decimal("3500"))
        self.assertEqual(case.outstanding, Decimal("1500"))
        self.assertEqual(case.status, "partial")

    def test_overpayment_is_rejected(self):
        response = self.client.post(
            reverse("payments:record_for_case", args=[self.case.pk]),
            {"amount": "6000", "payment_date": timezone.localdate().isoformat(), "mode": "cash"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_record_payment_from_unpaid_list(self):
        response = self.client.post(reverse("payments:record"), {
            "case": self.case.pk, "amount": "5000", "payment_date": timezone.localdate().isoformat(), "mode": "bank",
        })
        self.assertRedirects(response, self.case.get_absolute_url())
        self.assertEqual(Case.objects.get(pk=self.case.pk).payment_status, "paid")

    def test_edit_payment_allows_same_amount(self):
        payment = Payment.objects.create(case=self.case, amount=Decimal("5000"))
        response = self.client.post(reverse("payments:edit", args=[payment.pk]), {
            "amount": "5000", "payment_date": timezone.localdate().isoformat(), "mode": "cheque",
        })
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.mode, "cheque")


class ReminderTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.hospital = make_hospital()
        self.settings = AppSettings.load()  # 7,14,21 then every 7 days

    def test_not_due_before_first_reminder(self):
        case = make_case(self.doctor, self.hospital, days_ago=6)
        self.assertFalse(reminder_state(case).due)

    def test_due_after_first_reminder_and_cleared_by_followup(self):
        case = make_case(self.doctor, self.hospital, days_ago=8)
        self.assertTrue(reminder_state(case).due)
        PaymentFollowUp.objects.create(case=case, followup_date=timezone.localdate())
        self.assertFalse(reminder_state(case).due)

    def test_reminder_repeats_at_next_threshold(self):
        case = make_case(self.doctor, self.hospital, days_ago=15)
        PaymentFollowUp.objects.create(case=case, followup_date=case.case_date + datetime.timedelta(days=8))
        self.assertTrue(reminder_state(case).due)  # day 14 reminder is newer than the day 8 follow-up

    def test_repeat_interval_after_last_reminder(self):
        case = make_case(self.doctor, self.hospital, days_ago=29)
        PaymentFollowUp.objects.create(case=case, followup_date=case.case_date + datetime.timedelta(days=22))
        state = reminder_state(case)
        self.assertTrue(state.due)  # 21 + 7 = day 28
        self.assertEqual(state.last_trigger, case.case_date + datetime.timedelta(days=28))

    def test_snooze_hides_reminder(self):
        case = make_case(self.doctor, self.hospital, days_ago=10)
        self.client.force_login(self.doctor.user)
        self.client.post(reverse("payments:followup_snooze", args=[case.pk]), {"days": "3"})
        case.refresh_from_db()
        self.assertFalse(reminder_state(case).due)
        self.assertEqual(case.followup_snoozed_until, timezone.localdate() + datetime.timedelta(days=3))

    def test_promised_date_pauses_reminders(self):
        case = make_case(self.doctor, self.hospital, days_ago=10)
        self.client.force_login(self.doctor.user)
        promised = timezone.localdate() + datetime.timedelta(days=5)
        self.client.post(reverse("payments:followup_add", args=[case.pk]), {
            "followup_date": timezone.localdate().isoformat(), "method": "call",
            "promised_payment_date": promised.isoformat(), "notes": "Will pay Friday",
        })
        case.refresh_from_db()
        self.assertEqual(case.followup_snoozed_until, promised)

    def test_quick_mark_followed_up(self):
        case = make_case(self.doctor, self.hospital, days_ago=10)
        self.client.force_login(self.doctor.user)
        self.client.post(reverse("payments:followup_quick", args=[case.pk]))
        self.assertEqual(case.followups.count(), 1)
        self.assertFalse(reminder_state(Case.objects.get(pk=case.pk)).due)

    def test_paid_cases_never_need_followup(self):
        case = make_case(self.doctor, self.hospital, days_ago=50, fee=1000)
        Payment.objects.create(case=case, amount=Decimal("1000"))
        self.assertEqual(receivables_for(self.doctor.user), [])

    def test_receivables_sorted_oldest_first(self):
        newer = make_case(self.doctor, self.hospital, days_ago=5)
        older = make_case(self.doctor, self.hospital, days_ago=50)
        self.client.force_login(self.doctor.user)
        response = self.client.get(reverse("receivables:list"))
        self.assertEqual([c.pk for c in response.context["cases"]], [older.pk, newer.pk])
        response = self.client.get(reverse("receivables:list") + "?view=overdue")
        self.assertEqual([c.pk for c in response.context["cases"]], [older.pk])
