from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import ImportableModel, TimeStampedModel


class Payment(ImportableModel):
    """Money received against a case. A case can have many (partial) payments."""

    MODE_CHOICES = [
        ("upi", "UPI"),
        ("bank", "Bank transfer / NEFT"),
        ("cheque", "Cheque"),
        ("cash", "Cash"),
        ("card", "Card"),
        ("other", "Other"),
    ]

    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    payment_date = models.DateField(default=timezone.localdate, db_index=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="bank")
    reference_no = models.CharField("Transaction / cheque no.", max_length=100, blank=True)
    received_by = models.CharField(max_length=100, blank=True,
                                   help_text="Who received the payment, e.g. Dr. Mehta, clinic staff, bank account.")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"{self.amount} on {self.payment_date:%d %b %Y} ({self.get_mode_display()})"


class PaymentFollowUp(TimeStampedModel):
    """A record of chasing a hospital for an unpaid case."""

    METHOD_CHOICES = [
        ("call", "Phone call"),
        ("whatsapp", "WhatsApp (manual)"),
        ("email", "Email"),
        ("in_person", "In person"),
        ("sms", "SMS"),
        ("other", "Other"),
    ]

    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="followups")
    followup_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="call")
    contact = models.ForeignKey("contacts.Contact", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="followups", help_text="Who you spoke to.")
    contact_person = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    promised_payment_date = models.DateField(
        null=True, blank=True, help_text="If the hospital committed to a date, reminders pause until then."
    )
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-followup_date", "-id"]

    def __str__(self):
        return f"{self.get_method_display()} on {self.followup_date:%d %b %Y}"
