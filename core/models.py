from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ImportableModel(TimeStampedModel):
    """Adds fields that let us import legacy Excel records later without schema changes."""

    SOURCE_MANUAL = "manual"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = [(SOURCE_MANUAL, "Entered in app"), (SOURCE_IMPORT, "Imported (Excel)")]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    legacy_ref = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Row/sheet reference from the original Excel file, used to avoid duplicate imports.",
    )

    class Meta:
        abstract = True


def validate_reminder_days(value):
    try:
        days = [int(d) for d in value.split(",") if d.strip()]
    except ValueError:
        raise ValidationError("Enter whole numbers separated by commas, e.g. 7,14,21")
    if not days or any(d <= 0 for d in days):
        raise ValidationError("Enter at least one positive number of days.")


class AppSettings(models.Model):
    """Single-row table holding configurable business rules."""

    practice_name = models.CharField(max_length=120, default="Payments Tracker")
    default_payment_terms_days = models.PositiveIntegerField(
        default=30,
        help_text="Used when a case has no expected payment date: it becomes Overdue this many days after the case date.",
    )
    reminder_days = models.CharField(
        max_length=100, default="7,14,21", validators=[validate_reminder_days],
        help_text="Follow-up reminders are raised when an unpaid case reaches these ages (days after case date).",
    )
    repeat_reminder_every_days = models.PositiveIntegerField(
        default=7,
        help_text="After the last reminder above, keep reminding at this interval. 0 = stop.",
    )
    allow_signups = models.BooleanField(
        "Allow new doctors to sign up", default=True,
        help_text="Shows a 'Create an account' link on the sign-in page.",
    )
    signup_requires_approval = models.BooleanField(
        "New sign-ups need admin approval", default=False,
        help_text="New accounts stay inactive until an admin ticks 'Active' on the Doctors page.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App settings"
        verbose_name_plural = "App settings"

    def __str__(self):
        return "App settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def reminder_days_list(self):
        return sorted({int(d) for d in self.reminder_days.split(",") if d.strip()})
