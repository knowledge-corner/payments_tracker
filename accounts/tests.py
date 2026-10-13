from django.test import TestCase
from django.urls import reverse

from cases.models import Case
from core.models import AppSettings
from core.practice import CODE_COOKIE, WHO_COOKIE
from core.testing import enter_practice, make_admin, make_case, make_doctor, make_hospital

from .forms import doctor_title
from .models import Doctor


class DoctorTitleTests(TestCase):
    def test_doctor_title(self):
        self.assertEqual(doctor_title("anjali mehta"), "Dr. Anjali Mehta")
        self.assertEqual(doctor_title("Dr. Vikram Rao"), "Dr. Vikram Rao")
        self.assertEqual(doctor_title("dr vikram"), "Dr. Vikram")


class PracticeAccessTests(TestCase):
    """Organisation-level access: practice code once per phone, everyone sees and edits everything."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # wrong-code attempt counters
        settings_obj = AppSettings.load()
        settings_obj.practice_code = "482913"
        settings_obj.save()
        self.mehta = make_doctor("dr.mehta", "Dr. Anjali Mehta")
        self.rao = make_doctor("dr.rao", "Dr. Vikram Rao")

    def test_everything_asks_for_the_code_first(self):
        for url in ("/", "/cases/", "/reports/", "/cases/add/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(reverse("practice_enter")), url)
        self.assertContains(self.client.get(reverse("practice_enter")), "Practice code")

    def test_wrong_code_then_right_code_then_who(self):
        response = self.client.post(reverse("practice_enter"), {"code": "000000"})
        self.assertContains(response, "not right")
        response = self.client.post(reverse("practice_enter"), {"code": "482913"})
        self.assertTrue(response["Location"].startswith(reverse("practice_who")))
        self.assertIn(CODE_COOKIE, response.cookies)
        self.assertGreater(int(response.cookies[CODE_COOKIE]["max-age"]), 60 * 60 * 24 * 365)  # remembered
        response = self.client.post(reverse("practice_who"), {"doctor": self.rao.pk})
        self.assertEqual(response.cookies[WHO_COOKIE].value, str(self.rao.pk))
        self.assertContains(self.client.get("/"), "Dr. Vikram Rao")
        # later visits: straight in
        self.assertEqual(self.client.get("/cases/").status_code, 200)

    def test_who_can_add_a_new_name(self):
        enter_practice(self.client)
        self.client.post(reverse("practice_who"), {"new_name": "neha joshi", "new_phone": "9822000000"})
        self.assertTrue(Doctor.objects.filter(display_name="Dr. Neha Joshi", user__isnull=True).exists())

    def test_everyone_sees_and_edits_all_cases(self):
        hospital = make_hospital()
        theirs = make_case(self.rao, hospital, patient_reference="RAO-1")
        enter_practice(self.client, self.mehta)
        self.assertContains(self.client.get(reverse("cases:list")), "RAO-1")
        response = self.client.post(reverse("cases:edit", args=[theirs.pk]), {
            "doctor": self.rao.pk, "hospital": hospital.pk, "case_date": theirs.case_date.isoformat(),
            "fee": "7777", "due_date": theirs.due_date.isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Case.objects.get(pk=theirs.pk).fee, 7777)
        self.client.post(reverse("cases:delete", args=[theirs.pk]))
        self.assertFalse(Case.objects.filter(pk=theirs.pk).exists())

    def test_changing_code_locks_other_phones_but_not_this_one(self):
        other = self.client_class()
        enter_practice(other, self.rao)
        enter_practice(self.client, self.mehta)
        response = self.client.post(reverse("practice_settings"), {"new_code": "777888", "confirm_code": "777888"})
        self.assertEqual(AppSettings.load().practice_code, "777888")
        self.client.cookies[CODE_COOKIE] = response.cookies[CODE_COOKIE].value
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(other.get("/").status_code, 302)  # old code -> asked again

    def test_practice_settings_shows_code_to_everyone_inside(self):
        enter_practice(self.client, self.mehta)
        self.assertContains(self.client.get(reverse("practice_settings")), "482913")

    def test_lock_this_phone(self):
        enter_practice(self.client, self.mehta)
        self.client.post(reverse("practice_lock"))
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_admin_sign_in_without_code_can_reset_it(self):
        admin = make_admin()
        response = self.client.post(reverse("practice_admin_login"), {"username": admin.username, "password": "Pass@12345"})
        self.assertRedirects(response, reverse("practice_settings"))
        self.assertContains(self.client.get(reverse("practice_settings")), "482913")
        self.client.post(reverse("practice_settings"), {"new_code": "ABCD12", "confirm_code": "ABCD12"})
        self.assertEqual(AppSettings.load().practice_code, "ABCD12")

    def test_doctor_login_cannot_use_admin_sign_in(self):
        response = self.client.post(reverse("practice_admin_login"), {"username": "dr.mehta", "password": "Pass@12345"})
        self.assertContains(response, "not right")

    def test_code_not_set_yet(self):
        AppSettings.objects.update(practice_code="")
        self.assertContains(self.client.get(reverse("practice_enter")), "has not been set yet")

    def test_too_many_wrong_codes(self):
        for _ in range(8):
            self.client.post(reverse("practice_enter"), {"code": "111111"})
        response = self.client.post(reverse("practice_enter"), {"code": "482913"})
        self.assertContains(response, "Too many wrong tries")

    def test_set_practice_code_command(self):
        import io

        from django.core.management import call_command

        call_command("set_practice_code", "555444", stdout=io.StringIO())
        self.assertEqual(AppSettings.load().practice_code, "555444")


class AnaesthetistManagementTests(TestCase):
    def test_add_anaesthetist_without_login(self):
        enter_practice(self.client)
        response = self.client.post(reverse("accounts:doctor_add"), {
            "display_name": "neha joshi", "phone": "9822000000", "specialisation": "Anaesthesiology", "is_active": "on",
        })
        self.assertRedirects(response, reverse("accounts:doctor_list"))
        doctor = Doctor.objects.get(display_name="Dr. Neha Joshi")
        self.assertIsNone(doctor.user)
        self.assertContains(self.client.get(reverse("accounts:doctor_list")), "Dr. Neha Joshi")
