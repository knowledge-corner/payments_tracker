"""Who to call about a case.

Contacts are shared by the whole practice.
Order: the case's own contact -> the main contact for that hospital
-> the most recent contact there -> the hospital's main phone.
"""
import re
from dataclasses import dataclass

from .models import Contact, ContactAffiliation, Surgeon


def surgeon_name_key(name):
    """'Dr. A  Shah', 'dr a shah' and 'A. Shah' all give 'a shah'."""
    name = re.sub(r"^\s*dr\.?\s+", "", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def find_surgeon(name):
    """The practice's existing surgeon with this name (ignoring Dr., dots and spacing), if any."""
    key = surgeon_name_key(name)
    if not key:
        return None
    exact = Surgeon.objects.filter(name__iexact=name.strip()).first()
    if exact:
        return exact
    return next((s for s in Surgeon.objects.order_by("-is_active", "pk") if surgeon_name_key(s.name) == key), None)


@dataclass
class CallTarget:
    name: str
    phone: str
    detail: str = ""
    contact_id: int | None = None

    @property
    def label(self):
        return f"{self.name} ({self.detail})" if self.detail else self.name


def _rank(link):
    """Main contact first, then the most recently added."""
    return (0 if link.is_primary else 1, -link.start_date.toordinal())


def best_contact(links):
    usable = [link for link in links if link.contact.best_phone]
    if not usable:
        return None
    return sorted(usable, key=_rank)[0]


def attach_call_targets(cases):
    """Sets `case.call` (CallTarget or None) on every case, with two queries in total."""
    cases = list(cases)
    if not cases:
        return cases
    hospital_ids = {c.hospital_id for c in cases}
    contact_ids = {c.contact_id for c in cases if c.contact_id}
    contacts = {c.pk: c for c in Contact.objects.filter(pk__in=contact_ids, is_active=True)}
    links = {}
    for link in (ContactAffiliation.objects.current()
                 .filter(hospital_id__in=hospital_ids)
                 .select_related("contact")):
        links.setdefault(link.hospital_id, []).append(link)
    for case in cases:
        case.call = None
        own = contacts.get(case.contact_id)
        if own and own.best_phone:
            case.call = CallTarget(own.name, own.best_phone, own.get_role_display(), own.pk)
            continue
        link = best_contact(links.get(case.hospital_id, []))
        if link:
            case.call = CallTarget(link.contact.name, link.contact.best_phone, link.contact.get_role_display(),
                                   link.contact_id)
        elif case.hospital.phone:
            case.call = CallTarget(case.hospital.name, case.hospital.phone.split(",")[0].split("/")[0].strip(),
                                   "hospital")
    return cases


def contacts_for_hospital(hospital_id):
    """Practice contacts ordered for a picker: working at this hospital (main contact first), then others."""
    links = list(ContactAffiliation.objects.current().filter(hospital_id=hospital_id)
                 .select_related("contact"))
    linked = {}
    for link in sorted(links, key=_rank):
        linked.setdefault(link.contact_id, link)
    here = [(link.contact, link) for link in linked.values()]
    others = Contact.objects.filter(is_active=True).exclude(pk__in=linked.keys()).order_by("name")
    return here, list(others)


def ensure_affiliation(contact, hospital):
    """Make sure a contact is recorded as working at this hospital (used when picked on a case)."""
    if ContactAffiliation.objects.filter(contact=contact, hospital=hospital, end_date__isnull=True).exists():
        return
    is_first = not ContactAffiliation.objects.current().filter(hospital=hospital).exists()
    ContactAffiliation.objects.create(contact=contact, hospital=hospital, is_primary=is_first)
