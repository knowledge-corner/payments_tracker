from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cases.models import Case
from core.testing import make_case, make_contact, make_doctor, make_hospital
from hospitals.models import Department

from .models import Contact, ContactAffiliation, Surgeon
from .services import attach_call_targets


class CallTargetTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.hospital = make_hospital("Call Test Hospital", phone="020-1111111 / 020-2222222")
        self.ortho = Department.objects.get(name="Orthopaedics")
        self.ent = Department.objects.get(name="ENT")

    def call_for(self, case):
        return attach_call_targets([Case.objects.select_related("hospital").get(pk=case.pk)])[0].call

    def test_falls_back_to_hospital_phone(self):
        call = self.call_for(make_case(self.doctor, self.hospital))
        self.assertEqual((call.name, call.phone), ("Call Test Hospital", "020-1111111"))

    def test_department_contact_beats_general_contact(self):
        make_contact(self.doctor, "General Desk", "+91 90000 00010", self.hospital)
        make_contact(self.doctor, "Ortho Billing", "+91 90000 00011", self.hospital, self.ortho)
        self.assertEqual(self.call_for(make_case(self.doctor, self.hospital, department=self.ortho)).name, "Ortho Billing")
        self.assertEqual(self.call_for(make_case(self.doctor, self.hospital, department=self.ent)).name, "General Desk")

    def test_case_contact_wins(self):
        make_contact(self.doctor, "Ortho Billing", "+91 90000 00011", self.hospital, self.ortho)
        own = make_contact(self.doctor, "Specific Person", "+91 90000 00012")
        case = make_case(self.doctor, self.hospital, department=self.ortho, contact=own)
        self.assertEqual(self.call_for(case).name, "Specific Person")

    def test_contacts_are_private_and_ended_links_ignored(self):
        other = make_doctor("dr.other", "Dr. Other")
        make_contact(other, "Someone Else's", "+91 90000 00013", self.hospital)
        old = make_contact(self.doctor, "Left the job", "+91 90000 00014", self.hospital)
        old.affiliations.update(end_date=timezone.localdate())
        self.assertEqual(self.call_for(make_case(self.doctor, self.hospital)).name, "Call Test Hospital")


class ContactViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.other = make_doctor("dr.other", "Dr. Other")
        self.hospital = make_hospital("Contact View Hospital")
        self.client.force_login(self.doctor.user)

    def test_add_contact_with_hospital_link(self):
        response = self.client.post(reverse("contacts:add"), {
            "name": "Mr. Kulkarni", "phone": "+91 98220 00000", "role": "billing",
            "link-hospital": self.hospital.pk, "link-start_date": timezone.localdate().isoformat(),
            "link-is_primary": "on",
        })
        contact = Contact.objects.get(name="Mr. Kulkarni")
        self.assertRedirects(response, contact.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(contact.doctor, self.doctor)
        self.assertEqual(contact.affiliations.get().hospital, self.hospital)

    def test_cannot_see_other_doctors_contacts(self):
        theirs = make_contact(self.other, "Private Person")
        self.assertEqual(self.client.get(theirs.get_absolute_url()).status_code, 403)
        self.assertNotContains(self.client.get(reverse("contacts:list")), "Private Person")

    def test_contact_moves_hospital(self):
        contact = make_contact(self.doctor, hospital=self.hospital)
        new = make_hospital("New Workplace")
        self.client.post(reverse("contacts:link_add", args=[contact.pk]), {
            "link-hospital": new.pk, "link-start_date": timezone.localdate().isoformat(), "link-moved_from_others": "on",
        })
        self.assertEqual([a.hospital for a in ContactAffiliation.objects.current().filter(contact=contact)], [new])
        self.assertEqual(contact.affiliations.count(), 2)  # history kept

    def test_end_link(self):
        contact = make_contact(self.doctor, hospital=self.hospital)
        link = contact.affiliations.get()
        self.client.post(reverse("contacts:link_end", args=[contact.pk, link.pk]))
        link.refresh_from_db()
        self.assertIsNotNone(link.end_date)

    def test_for_hospital_json(self):
        here = make_contact(self.doctor, "At Hospital", hospital=self.hospital)
        make_contact(self.doctor, "Elsewhere")
        make_contact(self.other, "Not Mine", hospital=self.hospital)
        surgeon = Surgeon.objects.create(doctor=self.doctor, name="Dr. Kulkarni")
        surgeon.link_hospital(self.hospital)
        Surgeon.objects.create(doctor=self.doctor, name="Dr. Elsewhere")
        make_case(self.doctor, self.hospital, contact=here, surgeon=surgeon)
        data = self.client.get(reverse("contacts:for_hospital"), {"hospital": self.hospital.pk}).json()
        self.assertEqual([c["id"] for c in data["here"]], [here.pk])
        self.assertEqual([c["label"].split(" - ")[0] for c in data["others"]], ["Elsewhere"])
        self.assertEqual([s["label"] for s in data["surgeons_here"]], ["Dr. Kulkarni"])
        self.assertEqual([s["label"] for s in data["surgeons_others"]], ["Dr. Elsewhere"])
        self.assertEqual(data["suggested_surgeon"], surgeon.pk)
        self.assertEqual(data["suggested_contact"], here.pk)


class CaseContactTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.hospital = make_hospital("Case Contact Hospital")
        self.client.force_login(self.doctor.user)

    def post_case(self, **extra):
        data = {"hospital": self.hospital.pk, "case_date": timezone.localdate().isoformat(), "fee": "5000"}
        data.update(extra)
        return self.client.post(reverse("cases:add"), data)

    def test_new_contact_created_and_linked(self):
        self.post_case(new_contact_name="Ms. Joshi", new_contact_phone="9876500000",
                       new_contact_role="billing")
        case = Case.objects.get()
        self.assertEqual(case.contact.name, "Ms. Joshi")
        self.assertEqual(case.contact.doctor, self.doctor)
        link = case.contact.affiliations.get()
        self.assertEqual((link.hospital, link.is_primary), (self.hospital, True))

    def test_new_contact_with_known_mobile_is_reused(self):
        existing = make_contact(self.doctor, "Mr. Patil", "+91 98765 00000")
        self.post_case(new_contact_name="Patil", new_contact_phone="9876500000")
        self.assertEqual(Case.objects.get().contact, existing)
        self.assertEqual(Contact.objects.count(), 1)

    def test_new_contact_needs_phone(self):
        response = self.post_case(new_contact_name="Ms. Joshi")
        self.assertIn("new_contact_phone", response.context["form"].errors)
        self.assertFalse(Case.objects.exists())

    def test_cannot_use_other_doctors_contact(self):
        theirs = make_contact(make_doctor("dr.other", "Dr. Other"), "Not Mine")
        response = self.post_case(contact=theirs.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Case.objects.exists())

    def test_missing_due_date_defaults_with_message(self):
        response = self.post_case()
        case = Case.objects.get()
        self.assertEqual((case.due_date - case.case_date).days, 30)
        response = self.client.get(response.url)
        self.assertContains(response, "30 days")

    def test_existing_contact_gets_linked_to_hospital(self):
        contact = make_contact(self.doctor, "Travelling Contact")
        self.post_case(contact=contact.pk)
        self.assertEqual(contact.affiliations.get().hospital, self.hospital)


class SurgeonTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.criticare = make_hospital("Criticare Test")
        self.hinduja = make_hospital("Hinduja Test")
        self.client.force_login(self.doctor.user)

    def post_case(self, hospital, **extra):
        data = {"hospital": hospital.pk, "case_date": timezone.localdate().isoformat(), "fee": "5000"}
        data.update(extra)
        return self.client.post(reverse("cases:add"), data)

    def test_patient_name_and_new_surgeon_linked_per_hospital(self):
        self.post_case(self.criticare, patient_name="Sunita Patil", new_surgeon_name="Dr. A Shah")
        self.post_case(self.hinduja, new_surgeon_name="dr. a  shah")  # same surgeon, other hospital
        surgeons = Surgeon.objects.filter(doctor=self.doctor)
        self.assertEqual(surgeons.count(), 1)
        surgeon = surgeons.get()
        self.assertEqual(set(surgeon.hospitals.all()), {self.criticare, self.hinduja})
        self.assertEqual(Case.objects.filter(surgeon=surgeon).count(), 2)
        self.assertEqual(Case.objects.get(hospital=self.criticare).patient_name, "Sunita Patil")

    def test_existing_surgeon_gets_hospital_link_once(self):
        surgeon = Surgeon.objects.create(doctor=self.doctor, name="Dr. B")
        self.post_case(self.criticare, surgeon=surgeon.pk)
        self.post_case(self.criticare, surgeon=surgeon.pk)
        self.assertEqual(surgeon.hospital_links.count(), 1)

    def test_surgeons_are_private(self):
        theirs = Surgeon.objects.create(doctor=make_doctor("dr.other", "Dr. Other"), name="Dr. Theirs")
        self.assertEqual(self.client.get(theirs.get_absolute_url()).status_code, 403)
        self.assertNotContains(self.client.get(reverse("contacts:surgeon_list")), "Dr. Theirs")
        response = self.post_case(self.criticare, surgeon=theirs.pk)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Case.objects.exists())

    def test_surgeon_pages(self):
        response = self.client.post(reverse("contacts:surgeon_add"), {
            "name": "Dr. C", "phone": "9822000000", "is_active": "on", "link-hospital": self.hinduja.pk})
        surgeon = Surgeon.objects.get(name="Dr. C")
        self.assertRedirects(response, surgeon.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(list(surgeon.hospitals.all()), [self.hinduja])
        self.client.post(reverse("contacts:surgeon_link_add", args=[surgeon.pk]), {"link-hospital": self.criticare.pk})
        self.assertEqual(surgeon.hospital_links.count(), 2)
        link = surgeon.hospital_links.get(hospital=self.criticare)
        self.client.post(reverse("contacts:surgeon_link_remove", args=[surgeon.pk, link.pk]))
        self.assertEqual(surgeon.hospital_links.count(), 1)
        self.assertContains(self.client.get(surgeon.get_absolute_url()), "Hinduja Test")
