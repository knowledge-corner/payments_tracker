"""Shared factories for tests."""
import datetime
from decimal import Decimal

from accounts.models import Doctor, User
from cases.models import Case
from hospitals.models import Hospital


def make_doctor(username="dr.test", name="Dr. Test"):
    user = User.objects.create_user(username=username, password="Pass@12345", role=User.ROLE_DOCTOR,
                                    email=f"{username}@example.com")
    return Doctor.objects.create(user=user, display_name=name)


def make_admin(username="boss"):
    return User.objects.create_user(username=username, password="Pass@12345", role=User.ROLE_ADMIN)


def make_hospital(name="Test Hospital", city="Pune", **kwargs):
    return Hospital.objects.create(name=name, city=city, **kwargs)


def make_contact(doctor, name="Mr. Patil", phone="+91 90000 00001", hospital=None, primary=True):
    from contacts.models import Contact, ContactAffiliation

    contact = Contact.objects.create(doctor=doctor, name=name, phone=phone)
    if hospital:
        ContactAffiliation.objects.create(contact=contact, hospital=hospital, is_primary=primary)
    return contact


def make_case(doctor, hospital, days_ago=0, fee=5000, **kwargs):
    from django.utils import timezone

    return Case.objects.create(
        doctor=doctor, hospital=hospital, fee=Decimal(fee),
        case_date=timezone.localdate() - datetime.timedelta(days=days_ago), **kwargs,
    )


def enter_practice(client, doctor=None, code="482913"):
    """Open the app like a remembered phone: valid practice-code cookie + 'who uses this phone'."""
    from django.core import signing

    from core.models import AppSettings
    from core.practice import CODE_COOKIE, WHO_COOKIE, fingerprint, practice_user

    settings_obj = AppSettings.load()
    if settings_obj.practice_code != code:
        settings_obj.practice_code = code
        settings_obj.save()
    client.cookies[CODE_COOKIE] = signing.get_cookie_signer(salt=CODE_COOKIE + CODE_COOKIE).sign(fingerprint(code))
    client.cookies[WHO_COOKIE] = str(doctor.pk) if doctor else "0"
    client.force_login(practice_user())
    return client
