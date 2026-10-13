from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_DOCTOR = "doctor"
    ROLE_CHOICES = [(ROLE_ADMIN, "Admin"), (ROLE_DOCTOR, "Doctor")]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DOCTOR)

    @property
    def is_app_admin(self):
        return self.is_superuser or self.role == self.ROLE_ADMIN

    @property
    def doctor_profile(self):
        return getattr(self, "doctor", None)

    def display_name(self):
        return self.get_full_name() or self.username


class DoctorQuerySet(models.QuerySet):
    def registered(self):
        """Anaesthetists who have joined: an active profile with an active login."""
        return self.filter(is_active=True, user__isnull=False, user__is_active=True)


class Doctor(TimeStampedModel):
    """An anaesthetist of the practice. Everyone signs in with their own login; the
    link to a login can be empty for names that came from an older shared-access version."""

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="doctor")
    display_name = models.CharField("Name", max_length=120, help_text="Name shown in the app, e.g. Dr. Anjali Mehta")
    phone = models.CharField(max_length=20, blank=True)
    registration_no = models.CharField("Medical registration no.", max_length=50, blank=True)
    specialisation = models.CharField(max_length=100, default="Anaesthesiology")
    is_active = models.BooleanField(default=True)

    objects = DoctorQuerySet.as_manager()

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name
