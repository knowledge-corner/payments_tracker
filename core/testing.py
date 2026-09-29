"""Shared factories for tests."""
import datetime
from decimal import Decimal

from accounts.models import Doctor, User
from cases.models import Case
from hospitals.models import Hospital


def make_doctor(username="dr.test", name="Dr. Test"):
    user = User.objects.create_user(username=username, password="Pass@12345", role=User.ROLE_DOCTOR)
    return Doctor.objects.create(user=user, display_name=name)


def make_admin(username="boss"):
    return User.objects.create_user(username=username, password="Pass@12345", role=User.ROLE_ADMIN)


def make_hospital(name="Test Hospital", fee=5000, terms=30):
    return Hospital.objects.create(name=name, default_fee=Decimal(fee), payment_terms_days=terms)


def make_case(doctor, hospital, days_ago=0, fee=5000, **kwargs):
    from django.utils import timezone

    return Case.objects.create(
        doctor=doctor, hospital=hospital, fee=Decimal(fee),
        case_date=timezone.localdate() - datetime.timedelta(days=days_ago), **kwargs,
    )
