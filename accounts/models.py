from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_DOCTOR = "doctor"
    ROLE_CHOICES = [(ROLE_ADMIN, "Admin"), (ROLE_DOCTOR, "Doctor")]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_DOCTOR)

    # Set per request by core.middleware.AdminViewMiddleware when the user switched to "View as admin".
    admin_view = False

    @property
    def is_real_admin(self):
        return self.is_superuser or self.role == self.ROLE_ADMIN

    @property
    def is_app_admin(self):
        """Admin rights in the app: real admins, or anyone who chose "View as admin"."""
        return self.is_real_admin or self.admin_view

    @property
    def doctor_profile(self):
        return getattr(self, "doctor", None)

    def display_name(self):
        return self.get_full_name() or self.username


class Doctor(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor")
    display_name = models.CharField(max_length=120, help_text="Name shown in the app, e.g. Dr. Anjali Mehta")
    phone = models.CharField(max_length=20, blank=True)
    registration_no = models.CharField("Medical registration no.", max_length=50, blank=True)
    specialisation = models.CharField(max_length=100, default="Anaesthesiology")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name
