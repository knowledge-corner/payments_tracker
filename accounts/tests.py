from django.test import TestCase
from django.urls import reverse

from core.models import AppSettings
from core.testing import make_admin

from .forms import doctor_title
from .models import Doctor, User

VALID = {
    "full_name": "anjali  mehta", "phone": "+91 98220 10001", "email": "Anjali@Example.com",
    "registration_no": "MMC-1", "username": "dr.anjali", "password1": "Str0ng!Pass99",
    "password2": "Str0ng!Pass99", "agree": "on", "website": "",
}


class SignupTests(TestCase):
    def post(self, **changes):
        data = {**VALID, **changes}
        return self.client.post(reverse("signup"), data)

    def test_doctor_title(self):
        self.assertEqual(doctor_title("anjali mehta"), "Dr. Anjali Mehta")
        self.assertEqual(doctor_title("Dr. Vikram Rao"), "Dr. Vikram Rao")
        self.assertEqual(doctor_title("dr vikram"), "Dr. Vikram")

    def test_signup_creates_doctor_and_logs_in(self):
        response = self.post()
        self.assertRedirects(response, reverse("dashboard:home"))
        doctor = Doctor.objects.get()
        self.assertEqual(doctor.display_name, "Dr. Anjali Mehta")
        self.assertEqual(doctor.user.email, "anjali@example.com")
        self.assertEqual(doctor.user.role, User.ROLE_DOCTOR)
        self.assertFalse(doctor.user.is_staff)
        self.assertEqual(int(self.client.session["_auth_user_id"]), doctor.user.pk)
        # New doctor sees an empty dashboard, not anyone else's data
        self.assertEqual(self.client.get(reverse("dashboard:home")).context["outstanding"], 0)

    def test_login_page_links_to_signup(self):
        self.assertContains(self.client.get(reverse("login")), reverse("signup"))

    def test_validation_errors(self):
        User.objects.create_user("dr.anjali", "other@example.com", "x")
        response = self.post(password2="different")
        form = response.context["form"]
        self.assertIn("username", form.errors)
        self.assertIn("password2", form.errors)
        self.assertIn("agree", self.post(agree="").context["form"].errors)
        self.assertIn("password1", self.post(username="dr.new", password1="12345678", password2="12345678").context["form"].errors)
        self.assertEqual(Doctor.objects.count(), 0)

    def test_honeypot_blocks_bots(self):
        response = self.post(website="http://spam.example")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="dr.anjali").exists())

    def test_signups_can_be_closed(self):
        s = AppSettings.load()
        s.allow_signups = False
        s.save()
        self.assertRedirects(self.client.get(reverse("signup")), reverse("login"))
        self.assertNotContains(self.client.get(reverse("login")), reverse("signup"))

    def test_approval_flow(self):
        s = AppSettings.load()
        s.signup_requires_approval = True
        s.save()
        self.assertRedirects(self.post(), reverse("login"))
        user = User.objects.get(username="dr.anjali")
        self.assertFalse(user.is_active)

        response = self.client.post(reverse("login"), {"username": "dr.anjali", "password": "Str0ng!Pass99"})
        self.assertContains(response, "waiting for admin approval")
        wrong = self.client.post(reverse("login"), {"username": "dr.anjali", "password": "nope"})
        self.assertContains(wrong, "incorrect")

        admin = make_admin()
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("accounts:doctor_list")), "Awaiting approval")
        doctor = user.doctor
        self.client.post(reverse("accounts:doctor_edit", args=[doctor.pk]), {
            "display_name": doctor.display_name, "username": "dr.anjali", "email": user.email,
            "phone": doctor.phone, "registration_no": "", "specialisation": "Anaesthesiology", "is_active": "on",
        })
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "dr.anjali", "password": "Str0ng!Pass99"})
        self.assertRedirects(response, reverse("dashboard:home"))


class PasswordResetTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user("dr.reset", "reset@example.com", "OldPass!2026", role=User.ROLE_DOCTOR)
        Doctor.objects.create(user=self.user, display_name="Reset", phone="+91 98220 12345")
        self.url = reverse("password_reset")
        self.good = {"username": "Dr.Reset", "mobile": "098220-12345", "email": "RESET@example.com"}

    def test_login_page_has_forgot_password_and_install(self):
        page = self.client.get(reverse("login"))
        self.assertContains(page, self.url)
        self.assertContains(page, "data-install-app")

    def test_full_reset_flow_without_email(self):
        from django.core import mail

        response = self.client.post(self.url, self.good)
        self.assertRedirects(response, reverse("password_reset_new"))
        self.assertContains(self.client.get(reverse("password_reset_new")), "dr.reset")
        response = self.client.post(reverse("password_reset_new"), {
            "new_password1": "BrandNew!2026", "new_password2": "BrandNew!2026",
        })
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew!2026"))
        self.assertEqual(len(mail.outbox), 0)
        # the verification can't be reused
        self.assertRedirects(self.client.get(reverse("password_reset_new")), self.url)

    def test_passwords_must_match(self):
        self.client.post(self.url, self.good)
        response = self.client.post(reverse("password_reset_new"), {
            "new_password1": "BrandNew!2026", "new_password2": "Different!2026",
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass!2026"))

    def test_every_detail_must_match(self):
        for field, wrong in (("username", "dr.other"), ("mobile", "9822099999"), ("email", "other@example.com")):
            data = dict(self.good, **{field: wrong})
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 200, field)
            self.assertContains(response, "don&#x27;t match our records")
        self.assertRedirects(self.client.get(reverse("password_reset_new")), self.url)

    def test_cannot_jump_to_new_password_page(self):
        self.assertRedirects(self.client.get(reverse("password_reset_new")), self.url)

    def test_locked_after_too_many_attempts(self):
        bad = dict(self.good, mobile="9000000000")
        for _ in range(5):
            self.client.post(self.url, bad)
        response = self.client.post(self.url, self.good)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many attempts")
