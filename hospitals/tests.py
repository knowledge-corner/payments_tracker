import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cases.models import Case
from core.testing import make_admin, make_case, make_contact, make_doctor, make_hospital

from .directory import import_directory, merge_hospitals
from .models import Department, Hospital


class DirectorySeedTests(TestCase):
    def test_starter_hospitals_and_departments_loaded_by_migrations(self):
        self.assertGreater(Hospital.objects.filter(source="starter").count(), 80)
        self.assertTrue(Hospital.objects.filter(city="Pune").exists())
        self.assertTrue(Hospital.objects.filter(city="Mumbai").exists())
        self.assertTrue(Department.objects.filter(name="Orthopaedics").exists())

    def test_search_matches_every_word_and_aliases(self):
        names = set(Hospital.objects.active().search("ruby hall").values_list("name", flat=True))
        self.assertIn("Ruby Hall Clinic", names)
        self.assertTrue(Hospital.objects.active().search("kem").exists())
        self.assertFalse(Hospital.objects.active().search("zzz-no-such").exists())


class HospitalViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.client.force_login(self.doctor.user)

    def test_search_endpoint_lists_my_hospitals_first(self):
        mine = make_hospital("Sahyadri Test Hospital", area="Kothrud")
        make_case(self.doctor, mine)
        data = self.client.get(reverse("hospitals:search")).json()
        self.assertEqual(data["results"][0]["id"], mine.pk)
        self.assertTrue(data["results"][0]["mine"])
        data = self.client.get(reverse("hospitals:search"), {"q": "sahyadri test"}).json()
        self.assertEqual([r["id"] for r in data["results"]], [mine.pk])

    def test_add_hospital_warns_about_duplicates(self):
        existing = make_hospital("Lotus Care Hospital", city="Pune")
        url = reverse("hospitals:add")
        response = self.client.post(url, {"name": "Lotus Care Hospital", "city": "Pune", "category": "hospital"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(existing, response.context["form"].similar)
        self.assertEqual(Hospital.objects.filter(name="Lotus Care Hospital").count(), 1)

        response = self.client.post(url + "?next=/cases/add/", {
            "name": "Lotus Care Hospital", "city": "Pune", "category": "hospital", "confirm_new": "on",
            "next": "/cases/add/",
        })
        added = Hospital.objects.filter(name="Lotus Care Hospital").latest("pk")
        self.assertRedirects(response, f"/cases/add/?hospital={added.pk}", fetch_redirect_response=False)
        self.assertEqual(added.source, "doctor")
        self.assertFalse(added.verified)
        self.assertEqual(added.created_by, self.doctor.user)

    def test_doctor_cannot_edit_verified_or_others_hospitals(self):
        hospital = make_hospital("Shared Hospital", verified=True)
        self.assertEqual(self.client.get(reverse("hospitals:edit", args=[hospital.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("hospitals:merge", args=[hospital.pk])).status_code, 403)

    def test_list_shows_my_hospitals_and_directory_search(self):
        mine = make_hospital("My Own Hospital")
        make_case(self.doctor, mine)
        response = self.client.get(reverse("hospitals:list"))
        self.assertContains(response, "My Own Hospital")
        self.assertNotContains(response, "Ruby Hall Clinic")
        self.assertContains(self.client.get(reverse("hospitals:list"), {"q": "ruby"}), "Ruby Hall Clinic")


class MergeAndImportTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.doctor = make_doctor()

    def test_merge_moves_cases_and_contacts(self):
        keep = make_hospital("Jehangir Hospital Test")
        dup = make_hospital("Jehangir Hosp. Test")
        case = make_case(self.doctor, dup)
        contact = make_contact(self.doctor, hospital=dup)
        self.assertEqual(merge_hospitals(dup, keep), 1)
        case.refresh_from_db()
        dup.refresh_from_db()
        keep.refresh_from_db()
        self.assertEqual(case.hospital, keep)
        self.assertEqual(contact.affiliations.get().hospital, keep)
        self.assertEqual(dup.merged_into, keep)
        self.assertFalse(Hospital.objects.active().filter(pk=dup.pk).exists())
        self.assertIn("Jehangir Hosp. Test", keep.aliases)

    def test_merge_view_admin_only(self):
        keep, dup = make_hospital("Keep Me"), make_hospital("Dup Me")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("hospitals:merge", args=[dup.pk]), {"target": keep.pk})
        self.assertRedirects(response, keep.get_absolute_url(), fetch_redirect_response=False)
        # old links keep working
        self.assertRedirects(self.client.get(dup.get_absolute_url()), keep.get_absolute_url(),
                             fetch_redirect_response=False)

    CSV = (
        "Sr_No,Hospital_Name,Hospital_Category,Discipline_Systems_of_Medicine,State,District,Location,"
        "Address_Original_First_Line,Pincode,Telephone\n"
        "101,SUNRISE MULTISPECIALITY HOSPITAL,Private,Allopathy,Maharashtra,Pune,Baner,Baner Road,411045,020-1234567\n"
        "102,GREEN AYURVED CLINIC,Private,Ayurveda,Maharashtra,Pune,Aundh,,411007,\n"
        "103,SEA VIEW HOSPITAL,Public/ Government,Allopathy,Maharashtra,Mumbai Suburban,Andheri,,400053,\n"
        "104,FAR AWAY HOSPITAL,Private,Allopathy,Maharashtra,Nagpur,Nagpur,,440001,\n"
        "105,Ruby Hall Clinic,Private,Allopathy,Maharashtra,Pune,Sassoon Road,40 Sassoon Road,411001,020-66455100\n"
    )

    def test_import_directory_filters_and_is_repeatable(self):
        counts = import_directory(io.BytesIO(self.CSV.encode()), ["Pune", "Mumbai Suburban"])
        self.assertEqual(counts["matched"], 4)
        self.assertEqual(counts["skipped_system"], 1)
        self.assertEqual(counts["created"], 2)
        self.assertEqual(counts["updated"], 1)  # starter "Ruby Hall Clinic" upgraded
        sunrise = Hospital.objects.get(name="Sunrise Multispeciality Hospital")
        self.assertEqual((sunrise.city, sunrise.area, sunrise.pincode, sunrise.source), ("Pune", "Baner", "411045", "directory"))
        self.assertEqual(Hospital.objects.get(name="Sea View Hospital").city, "Mumbai")
        self.assertEqual(Hospital.objects.get(name="Sea View Hospital").ownership, "government")
        self.assertFalse(Hospital.objects.filter(name__icontains="Far Away").exists())
        ruby = Hospital.objects.get(name="Ruby Hall Clinic", city="Pune")
        self.assertEqual((ruby.source, ruby.phone), ("directory", "020-66455100"))

        total = Hospital.objects.count()
        again = import_directory(io.BytesIO(self.CSV.encode()), ["Pune", "Mumbai Suburban"])
        self.assertEqual((again["created"], again["updated"]), (0, 3))
        self.assertEqual(Hospital.objects.count(), total)

    def test_import_view(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile("hospitals.csv", self.CSV.encode(), content_type="text/csv")
        response = self.client.post(reverse("hospitals:directory_import"), {"file": upload, "districts": "Pune"})
        self.assertRedirects(response, reverse("hospitals:list"), fetch_redirect_response=False)
        self.assertTrue(Hospital.objects.filter(name="Sunrise Multispeciality Hospital").exists())
        self.assertFalse(Hospital.objects.filter(name="Sea View Hospital").exists())

    def test_import_view_admin_only(self):
        self.client.force_login(self.doctor.user)
        self.assertEqual(self.client.get(reverse("hospitals:directory_import")).status_code, 403)

    def test_cases_untouched_by_import(self):
        hospital = Hospital.objects.get(name="Ruby Hall Clinic", city="Pune")
        case = make_case(self.doctor, hospital)
        import_directory(io.BytesIO(self.CSV.encode()), ["Pune"])
        self.assertEqual(Case.objects.get(pk=case.pk).hospital_id, hospital.pk)
