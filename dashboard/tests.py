from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.testing import make_case, make_doctor, make_hospital
from payments.models import Payment


class DashboardTests(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)

    def test_totals(self):
        doctor = make_doctor()
        hospital = make_hospital(terms=30)
        paid = make_case(doctor, hospital, days_ago=0, fee=4000)
        Payment.objects.create(case=paid, amount=Decimal("4000"))
        make_case(doctor, hospital, days_ago=0, fee=3000)
        make_case(doctor, hospital, days_ago=60, fee=2000)  # overdue, older than this month
        other = make_doctor("dr.x", "Dr. X")
        make_case(other, hospital, fee=99999)  # must not leak into this doctor's figures

        self.client.force_login(doctor.user)
        ctx = self.client.get(reverse("dashboard:home") + "?period=all").context
        self.assertEqual(ctx["total_earnings"], Decimal("9000"))
        self.assertEqual(ctx["amount_received"], Decimal("4000"))
        self.assertEqual(ctx["outstanding"], Decimal("5000"))
        self.assertEqual(ctx["overdue_count"], 1)
        self.assertEqual(ctx["pending_count"], 1)
        self.assertGreaterEqual(ctx["followup_count"], 1)


class NavigationTests(TestCase):
    def test_bottom_nav_and_receivables_links(self):
        doctor = make_doctor()
        hospital = make_hospital(terms=30)
        make_case(doctor, hospital, days_ago=60, fee=2000)  # overdue
        make_case(doctor, hospital, days_ago=2, fee=1000)   # pending
        self.client.force_login(doctor.user)
        page = self.client.get(reverse("dashboard:home")).content.decode()
        nav = page[page.index('class="bottom-nav'):]
        nav = nav[:nav.index("</nav>")]
        labels = [label for label in ("Dashboard", "Cases", "Add Case", "Hospitals", "Reports", "Receivables") if label in nav]
        self.assertEqual(labels, ["Dashboard", "Cases", "Add Case", "Hospitals", "Reports"])
        self.assertLess(nav.index("Cases"), nav.index("Add Case"))
        self.assertLess(nav.index("Add Case"), nav.index("Hospitals"))
        for view in ("pending", "overdue", "followup"):
            self.assertIn(f"/receivables/?view={view}", page)
        pending = self.client.get(reverse("receivables:list") + "?view=pending")
        self.assertEqual(len(pending.context["cases"]), 1)
        self.assertContains(pending, "Pending payments")
        self.assertContains(pending, 'aria-label="Back to dashboard"')

    def test_reports_offer_excel_only(self):
        self.client.force_login(make_doctor().user)
        page = self.client.get(reverse("reports:cases"))
        self.assertContains(page, "export=xlsx")
        self.assertNotContains(page, "export=csv")
