from django.test import TestCase
from django.urls import reverse

from core.templatetags.money import inr
from core.testing import make_admin, make_doctor


class CoreTests(TestCase):
    def test_indian_number_format(self):
        self.assertEqual(inr(1234567), "₹12,34,567")
        self.assertEqual(inr("999"), "₹999")
        self.assertEqual(inr(None), "₹0")

    def test_pwa_endpoints(self):
        manifest = self.client.get(reverse("manifest"))
        self.assertEqual(manifest["Content-Type"], "application/manifest+json")
        self.assertEqual(manifest.json()["display"], "standalone")
        sw = self.client.get(reverse("service_worker"))
        self.assertEqual(sw["Content-Type"], "application/javascript")
        self.assertEqual(sw["Service-Worker-Allowed"], "/")
        self.assertEqual(self.client.get(reverse("health")).content, b"payments-tracker ok")

    def test_settings_admin_only(self):
        self.client.force_login(make_doctor().user)
        self.assertEqual(self.client.get(reverse("app_settings")).status_code, 403)
        self.client.force_login(make_admin())
        self.assertEqual(self.client.get(reverse("app_settings")).status_code, 200)


class DoctorManagementTests(TestCase):
    def test_admin_creates_doctor_with_login(self):
        self.client.force_login(make_admin())
        response = self.client.post(reverse("accounts:doctor_add"), {
            "display_name": "Dr. Neha Joshi", "username": "dr.joshi", "password": "Str0ng!Pass99",
            "specialisation": "Anaesthesiology", "is_active": "on",
        })
        self.assertRedirects(response, reverse("accounts:doctor_list"))
        self.assertTrue(self.client.login(username="dr.joshi", password="Str0ng!Pass99"))


class CsrfFailureTests(TestCase):
    def test_expired_login_page_redirects_back_with_message(self):
        from django.test import Client

        make_doctor()
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("login"), {"username": "dr.test", "password": "Pass@12345"}, follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "sign-in page had expired")

    def test_other_pages_show_friendly_page(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(make_doctor().user)
        response = client.post(reverse("cases:add"), {})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "This page expired", status_code=403)
