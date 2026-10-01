"""Who to call about a case.

Order: the case's own contact -> the doctor's main contact for that hospital
and department -> any contact for that department -> the hospital-wide
contact -> the hospital's main phone from the directory.
"""
from dataclasses import dataclass

from .models import Contact, ContactAffiliation


@dataclass
class CallTarget:
    name: str
    phone: str
    detail: str = ""
    contact_id: int | None = None

    @property
    def label(self):
        return f"{self.name} ({self.detail})" if self.detail else self.name


def _rank(link, department_id):
    same_dept = link.department_id == department_id and department_id is not None
    any_dept = link.department_id is None
    return (
        0 if same_dept else (1 if any_dept else 2),
        0 if link.is_primary else 1,
        -link.start_date.toordinal(),
    )


def best_contact(links, department_id):
    usable = [link for link in links if link.contact.best_phone]
    if not usable:
        return None
    return sorted(usable, key=lambda link: _rank(link, department_id))[0]


def attach_call_targets(cases):
    """Sets `case.call` (CallTarget or None) on every case, with two queries in total."""
    cases = list(cases)
    if not cases:
        return cases
    doctor_ids = {c.doctor_id for c in cases}
    hospital_ids = {c.hospital_id for c in cases}
    contact_ids = {c.contact_id for c in cases if c.contact_id}
    contacts = {c.pk: c for c in Contact.objects.filter(pk__in=contact_ids, is_active=True)}
    links = {}
    for link in (ContactAffiliation.objects.current()
                 .filter(contact__doctor_id__in=doctor_ids, hospital_id__in=hospital_ids)
                 .select_related("contact", "department")):
        links.setdefault((link.contact.doctor_id, link.hospital_id), []).append(link)
    for case in cases:
        case.call = None
        own = contacts.get(case.contact_id)
        if own and own.best_phone:
            case.call = CallTarget(own.name, own.best_phone, own.get_role_display(), own.pk)
            continue
        link = best_contact(links.get((case.doctor_id, case.hospital_id), []), case.department_id)
        if link:
            detail = link.department.name if link.department_id else link.contact.get_role_display()
            case.call = CallTarget(link.contact.name, link.contact.best_phone, detail, link.contact_id)
        elif case.hospital.phone:
            case.call = CallTarget(case.hospital.name, case.hospital.phone.split(",")[0].split("/")[0].strip(),
                                   "hospital")
    return cases


def contacts_for_hospital(doctor, hospital_id, department_id=None):
    """Doctor's contacts ordered for a picker: working at this hospital (department match first), then others."""
    links = list(ContactAffiliation.objects.current().filter(contact__doctor=doctor, hospital_id=hospital_id)
                 .select_related("contact", "department"))
    linked = {}
    for link in sorted(links, key=lambda link: _rank(link, department_id)):
        linked.setdefault(link.contact_id, link)
    here = [(link.contact, link) for link in linked.values()]
    others = Contact.objects.filter(doctor=doctor, is_active=True).exclude(pk__in=linked.keys()).order_by("name")
    return here, list(others)


def ensure_affiliation(contact, hospital, department=None):
    """Make sure a contact is recorded as working at this hospital (used when picked on a case)."""
    current = ContactAffiliation.objects.filter(contact=contact, hospital=hospital, end_date__isnull=True)
    if department is not None and current.filter(department=department).exists():
        return
    if department is None and current.exists():
        return
    if current.filter(department__isnull=True).exists():
        return
    is_first = not ContactAffiliation.objects.current().filter(
        contact__doctor=contact.doctor, hospital=hospital, department=department).exists()
    ContactAffiliation.objects.create(contact=contact, hospital=hospital, department=department, is_primary=is_first)
