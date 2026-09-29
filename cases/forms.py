from decimal import Decimal

from django import forms
from django.utils import timezone

from accounts.models import Doctor
from core.forms import StyledModelForm
from hospitals.models import Hospital
from payments.models import Payment

from .models import Case

COMMON_PROCEDURES = [
    "General anaesthesia (GA)",
    "Spinal anaesthesia",
    "Epidural",
    "Combined spinal-epidural (CSE)",
    "LSCS - spinal",
    "Peripheral nerve block",
    "Monitored anaesthesia care / sedation",
    "Labour analgesia",
    "Endoscopy sedation",
    "ICU / emergency call",
]


class HospitalSelect(forms.Select):
    """Adds data-fee to each <option> so the page can pre-fill the hospital's default fee."""

    def __init__(self, *args, **kwargs):
        self.fees = {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        key = str(getattr(value, "value", value))
        if key in self.fees:
            option["attrs"]["data-fee"] = f"{self.fees[key]:.0f}"
        return option


class CaseForm(StyledModelForm):
    paid_now = forms.BooleanField(
        required=False, label="Payment already received",
        help_text="Tick if the hospital/patient paid on the spot.",
    )
    paid_amount = forms.DecimalField(required=False, min_value=Decimal("0.01"), max_digits=10, decimal_places=2)
    paid_mode = forms.ChoiceField(choices=Payment.MODE_CHOICES, required=False, initial="upi", label="Mode")

    class Meta:
        model = Case
        fields = ["doctor", "hospital", "case_date", "patient_reference", "procedure_type", "fee", "due_date", "notes"]
        widgets = {
            "hospital": HospitalSelect(),
            "case_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fee": forms.NumberInput(attrs={"inputmode": "decimal", "step": "1"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "procedure_type": forms.TextInput(attrs={"list": "procedure-options", "autocomplete": "off"}),
            "patient_reference": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "e.g. IP 45821 / bill no."}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        hospitals = Hospital.objects.filter(is_active=True)
        if self.instance.pk:
            hospitals = Hospital.objects.filter(pk=self.instance.hospital_id) | hospitals
        self.fields["hospital"].queryset = hospitals.order_by("name")
        self.fields["hospital"].widget.fees = {str(h.pk): h.default_fee for h in hospitals}
        self.fields["hospital"].empty_label = "Select hospital"
        self.fields["fee"].widget.attrs["placeholder"] = "Fee"

        if user is not None and user.is_app_admin:
            self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True)
        else:
            self.fields.pop("doctor")

        if self.instance.pk:
            for name in ("paid_now", "paid_amount", "paid_mode"):
                self.fields.pop(name)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("paid_now"):
            amount = cleaned.get("paid_amount") or cleaned.get("fee")
            fee = cleaned.get("fee")
            if not amount:
                self.add_error("paid_amount", "Enter the amount received.")
            elif fee is not None and amount > fee:
                self.add_error("paid_amount", "Amount received cannot be more than the fee.")
            cleaned["paid_amount"] = amount
        case_date = cleaned.get("case_date")
        if case_date and case_date > timezone.localdate():
            self.add_error("case_date", "Case date cannot be in the future.")
        return cleaned
