from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel


class Contact(TimeStampedModel):
    """A person a doctor deals with for payments. Private to that doctor."""

    ROLE_CHOICES = [
        ("billing", "Billing"),
        ("accounts", "Accounts"),
        ("ot", "OT in-charge"),
        ("consultant", "Consultant / surgeon"),
        ("admin", "Administration"),
        ("other", "Other"),
    ]

    doctor = models.ForeignKey("accounts.Doctor", on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=100)
    phone = models.CharField("Mobile", max_length=20, blank=True)
    alt_phone = models.CharField("Other phone", max_length=20, blank=True)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="billing")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("contacts:detail", args=[self.pk])

    @property
    def best_phone(self):
        return self.phone or self.alt_phone

    def current_affiliations(self):
        return self.affiliations.filter(end_date__isnull=True).select_related("hospital", "department")


class AffiliationQuerySet(models.QuerySet):
    def current(self):
        return self.filter(end_date__isnull=True, contact__is_active=True)


class ContactAffiliation(TimeStampedModel):
    """Where (hospital + department) a contact handles payments - with history.

    When someone moves to another hospital, the old row gets an end date and a
    new row is added, so earlier cases still show who handled them.
    """

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="affiliations")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.CASCADE, related_name="contact_links")
    department = models.ForeignKey("hospitals.Department", null=True, blank=True, on_delete=models.SET_NULL,
                                   help_text="Leave empty if they handle all departments.")
    is_primary = models.BooleanField("Main contact", default=False)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)

    objects = AffiliationQuerySet.as_manager()

    class Meta:
        ordering = ["-is_primary", "-start_date"]

    def __str__(self):
        dept = f" ({self.department})" if self.department_id else ""
        return f"{self.contact} @ {self.hospital}{dept}"

    @property
    def is_current(self):
        return self.end_date is None


class SurgeonQuerySet(models.QuerySet):
    def for_user(self, user):
        qs = self.filter(is_active=True)
        return qs if user.is_app_admin else qs.filter(doctor__user=user)


class Surgeon(TimeStampedModel):
    """A surgeon who calls this anaesthetist. Private to the anaesthetist (doctor)."""

    doctor = models.ForeignKey("accounts.Doctor", on_delete=models.CASCADE, related_name="surgeons")
    name = models.CharField(max_length=100)
    phone = models.CharField("Mobile", max_length=20, blank=True)
    speciality = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    hospitals = models.ManyToManyField("hospitals.Hospital", through="SurgeonHospital", related_name="surgeons")

    objects = SurgeonQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("contacts:surgeon_detail", args=[self.pk])

    def link_hospital(self, hospital):
        """Record that this surgeon calls the doctor to `hospital` (one link per pair)."""
        if hospital is not None:
            SurgeonHospital.objects.get_or_create(surgeon=self, hospital=hospital)


class SurgeonHospital(TimeStampedModel):
    """Bridge table: one row per surgeon + hospital where they call the anaesthetist."""

    surgeon = models.ForeignKey(Surgeon, on_delete=models.CASCADE, related_name="hospital_links")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.CASCADE, related_name="surgeon_links")

    class Meta:
        ordering = ["hospital__name"]
        constraints = [models.UniqueConstraint(fields=["surgeon", "hospital"], name="unique_surgeon_hospital")]

    def __str__(self):
        return f"{self.surgeon} @ {self.hospital}"
