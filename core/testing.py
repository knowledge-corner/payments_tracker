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


def make_contact(doctor, name="Mr. Patil", phone="+91 90000 00001", hospital=None, department=None, primary=True):
    from contacts.models import Contact, ContactAffiliation

    contact = Contact.objects.create(doctor=doctor, name=name, phone=phone)
    if hospital:
        ContactAffiliation.objects.create(contact=contact, hospital=hospital, department=department, is_primary=primary)
    return contact


def make_case(doctor, hospital, days_ago=0, fee=5000, **kwargs):
    from django.utils import timezone

    return Case.objects.create(
        doctor=doctor, hospital=hospital, fee=Decimal(fee),
        case_date=timezone.localdate() - datetime.timedelta(days=days_ago), **kwargs,
    )
