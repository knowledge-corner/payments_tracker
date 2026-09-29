from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import ImportableModel


class Hospital(ImportableModel):
    name = models.CharField(max_length=150, unique=True)
    address = models.TextField("Location / address", blank=True)
    city = models.CharField(max_length=80, blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    default_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(0)],
        help_text="Pre-filled when this hospital is picked for a new case.",
    )
    payment_terms_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Days this hospital normally takes to pay. Leave blank to use the global setting.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
