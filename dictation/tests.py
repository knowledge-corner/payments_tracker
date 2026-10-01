import datetime
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from core.testing import make_contact, make_doctor
from hospitals.models import Hospital

from .parser import parse

TODAY = datetime.date(2026, 10, 1)


class ParserTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.ruby = Hospital.objects.get(name="Ruby Hall Clinic")
        self.patil = make_contact(self.doctor, "Mr. Patil", "9822012345", self.ruby)

    def fields(self, text):
        return parse(text, self.doctor, today=TODAY).as_json()["fields"]

    def test_full_sentence(self):
        f = self.fields("Ruby Hall ortho TKR under spinal IP 4521 fee 6,500 yesterday payment in 15 days contact Patil")
        self.assertEqual(f["hospital"]["id"], self.ruby.pk)
        self.assertEqual(f["case_date"], "2026-09-30")
        self.assertEqual(f["fee"], "6500")
        self.assertEqual(f["due_date"], "2026-10-15")
        self.assertEqual(f["procedure_type"], "TKR - Spinal")
        self.assertEqual(f["patient_reference"], "IP 4521")
        self.assertEqual(f["contact"], self.patil.pk)

    def test_branch_and_dates(self):
        f = self.fields("Sahyadri Kothrud, LSCS, ₹8000, 28th September, due on 15th November")
        self.assertEqual(f["hospital"]["label"], "Sahyadri Hospital Kothrud")
        self.assertEqual((f["case_date"], f["due_date"], f["fee"]), ("2026-09-28", "2026-11-15", "8000"))

    def test_new_contact_thousands_and_notes(self):
        f = self.fields("Jehangir today GA for lap chole fee 12k contact Mrs Shinde 98765 43210 notes patient anxious")
        self.assertEqual(f["hospital"]["label"], "Jehangir Hospital")
        self.assertEqual(f["fee"], "12000")
        self.assertEqual((f["new_contact_name"], f["new_contact_phone"]), ("Mrs Shinde", "9876543210"))
        self.assertEqual(f["notes"], "Patient anxious")

    def test_city_picks_right_branch_and_offers_alternatives(self):
        data = parse("KEM Mumbai cataract 3500 rupees", self.doctor, today=TODAY).as_json()
        self.assertEqual(data["fields"]["hospital"]["label"], "KEM Hospital Mumbai")
        self.assertIn("KEM Hospital Pune", [h["label"] for h in data["hospital_alternatives"]])

    def test_missing_fields_reported(self):
        data = parse("spinal yesterday", self.doctor, today=TODAY).as_json()
        self.assertEqual(data["missing"], ["hospital", "fee"])


class ParseViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.client.force_login(self.doctor.user)

    def test_parse_endpoint(self):
        response = self.client.post(reverse("dictation:parse"), json.dumps({"text": "Noble hospital fee 9000"}),
                                    content_type="application/json")
        self.assertEqual(response.json()["fields"]["hospital"]["label"], "Noble Hospital")

    def test_panel_on_add_case_only(self):
        self.assertContains(self.client.get(reverse("cases:add")), 'id="dictation"')

    @override_settings(FEATURE_DICTATION=False)
    def test_switched_off(self):
        response = self.client.get(reverse("cases:add"))
        self.assertNotContains(response, 'id="dictation"')
        self.assertNotContains(response, "dictation.js")
