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
