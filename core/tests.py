import io

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


class ResetAppDataTests(TestCase):
    def test_reset_keeps_users_and_doctors(self):
        from django.core.management import call_command

        from accounts.models import Doctor, User
        from cases.models import Case
        from contacts.models import Contact
        from core.testing import make_admin, make_case, make_contact, make_doctor, make_hospital
        from hospitals.models import Hospital

        doctor = make_doctor()
        make_admin()
        hospital = make_hospital("Temporary Hospital")
        make_case(doctor, hospital)
        make_contact(doctor, hospital=hospital)
        users = set(User.objects.values_list("username", "password"))

        call_command("reset_app_data", "--yes", stdout=io.StringIO())

        self.assertEqual(set(User.objects.values_list("username", "password")), users)
        self.assertTrue(Doctor.objects.filter(pk=doctor.pk).exists())
        self.assertFalse(Case.objects.exists())
        self.assertFalse(Contact.objects.exists())
        self.assertFalse(Hospital.objects.filter(name="Temporary Hospital").exists())
        self.assertGreater(Hospital.objects.filter(source="starter").count(), 80)


class AssetVersionTests(TestCase):
    def test_own_scripts_are_versioned(self):
        from core.assets import asset_version

        version = asset_version()
        self.assertEqual(len(version), 10)
        response = self.client.get(reverse("login"))
        self.assertContains(response, f"js/searchable-select.js?v={version}")
        sw = self.client.get("/sw.js").content.decode()
        self.assertIn(f"-{version}", sw)
        self.assertIn(f"searchable-select.js?v={version}", sw)


class AdminViewTests(TestCase):
    def setUp(self):
        from core.testing import make_case, make_hospital

        self.me = make_doctor()
        self.other = make_doctor("dr.other", "Dr. Other")
        make_case(self.other, make_hospital("Other's Hospital"), patient_reference="THEIRS-1")
        self.client.force_login(self.me.user)

    def test_any_doctor_can_switch_to_admin_view_and_back(self):
        cases = reverse("cases:list")
        self.assertNotContains(self.client.get(cases), "THEIRS-1")
        self.assertContains(self.client.get(reverse("dashboard:home")), "View as admin")
        self.assertEqual(self.client.get(reverse("accounts:doctor_list")).status_code, 403)

        self.client.post(reverse("toggle_admin_view"))
        self.assertContains(self.client.get(cases), "THEIRS-1")
        self.assertEqual(self.client.get(reverse("accounts:doctor_list")).status_code, 200)
        self.assertContains(self.client.get(reverse("dashboard:home")), "Back to my view")

        self.client.post(reverse("toggle_admin_view"))
        self.assertNotContains(self.client.get(cases), "THEIRS-1")

    def test_switch_needs_post(self):
        self.assertEqual(self.client.get(reverse("toggle_admin_view")).status_code, 405)

    def test_database_admin_panel_is_developer_only(self):
        from accounts.models import User

        app_admin = make_admin()
        app_admin.is_staff = True
        app_admin.save()
        for user in (self.me.user, app_admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/admin/").status_code, 302, user)  # sent to the admin login
            self.assertNotContains(self.client.get(reverse("dashboard:home")), "/admin/")
        self.client.force_login(self.me.user)
        self.client.post(reverse("toggle_admin_view"))
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        developer = User.objects.create_superuser("dev", "dev@example.com", "Dev@12345")
        self.client.force_login(developer)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
