"""Practice-wide sharing: merge duplicate surgeons (same name) and contacts (same mobile)
that different anaesthetists saved separately. Cases, links and follow-ups are moved
to the kept record, so nothing is lost."""
import re

from django.db import migrations


def _name_key(name):
    name = re.sub(r"^\s*dr\.?\s+", "", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def _phone_key(phone):
    return re.sub(r"\D", "", phone or "")[-10:]


def merge(apps, schema_editor):
    Surgeon = apps.get_model("contacts", "Surgeon")
    SurgeonHospital = apps.get_model("contacts", "SurgeonHospital")
    Contact = apps.get_model("contacts", "Contact")
    ContactAffiliation = apps.get_model("contacts", "ContactAffiliation")
    Case = apps.get_model("cases", "Case")
    FollowUp = apps.get_model("payments", "PaymentFollowUp")

    keep = {}
    for s in Surgeon.objects.order_by("pk"):
        key = _name_key(s.name)
        if not key:
            continue
        if key not in keep:
            keep[key] = s
            continue
        k = keep[key]
        Case.objects.filter(surgeon=s).update(surgeon=k)
        existing = set(SurgeonHospital.objects.filter(surgeon=k).values_list("hospital_id", flat=True))
        for link in SurgeonHospital.objects.filter(surgeon=s):
            if link.hospital_id in existing:
                link.delete()
            else:
                link.surgeon = k
                link.save()
        if not k.phone and s.phone:
            k.phone = s.phone
            k.save()
        s.delete()

    keep = {}
    for c in Contact.objects.order_by("pk"):
        key = _phone_key(c.phone) or _phone_key(c.alt_phone)
        if len(key) < 10:
            continue
        if key not in keep:
            keep[key] = c
            continue
        k = keep[key]
        Case.objects.filter(contact=c).update(contact=k)
        FollowUp.objects.filter(contact=c).update(contact=k)
        ContactAffiliation.objects.filter(contact=c).update(contact=k)
        c.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0004_alter_contact_doctor_alter_surgeon_doctor"),
        ("cases", "0005_remove_case_department"),
        ("payments", "0004_paymentfollowup_next_reminder_and_more"),
    ]

    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
