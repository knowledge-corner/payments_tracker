import json
from pathlib import Path

from django.db import migrations

DEPARTMENTS = [
    "General Surgery", "Orthopaedics", "Obstetrics & Gynaecology", "ENT", "Ophthalmology", "Urology",
    "Cardiac / Cardiothoracic", "Neurosurgery", "Paediatric Surgery", "Plastic Surgery",
    "Dental / Maxillofacial", "Endoscopy / GI", "Oncology", "ICU / Emergency", "Other",
]


def seed(apps, schema_editor):
    Department = apps.get_model("hospitals", "Department")
    for order, name in enumerate(DEPARTMENTS, start=1):
        Department.objects.get_or_create(name=name, defaults={"sort_order": order * 10})

    Hospital = apps.get_model("hospitals", "Hospital")
    if Hospital.objects.exists():
        return  # existing install: use `manage.py reset_app_data --yes` for a clean start
    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "starter_hospitals.json").read_text("utf-8"))
    Hospital.objects.bulk_create([
        Hospital(name=row["name"], area=row.get("area", ""), city=row["city"], ownership=row.get("ownership", ""),
                 aliases=row.get("aliases", ""), source="starter", category="hospital",
                 district=row["city"])
        for row in data
    ])


class Migration(migrations.Migration):
    dependencies = [("hospitals", "0002_department_remove_hospital_contact_number_and_more")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
