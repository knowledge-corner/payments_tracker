from django import forms
from django.utils import timezone

from core.forms import StyledModelForm

from .models import Payment, PaymentFollowUp


class CaseChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, case):
        ref = f" · {case.patient_reference}" if case.patient_reference else ""
        return f"{case.hospital.name} · {case.case_date:%d %b %Y}{ref} · due {case.outstanding:,.0f}"


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = ["case", "amount", "payment_date", "mode", "reference_no", "notes"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "amount": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, case_queryset=None, fixed_case=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixed_case = fixed_case
        if fixed_case is not None:
            self.fields.pop("case")
        else:
            self.fields["case"] = CaseChoiceField(
                queryset=case_queryset, empty_label="Select an unpaid case",
                widget=forms.Select(attrs={"class": "form-select"}),
            )

    def _case(self):
        return self.fixed_case or self.cleaned_data.get("case")

    def clean_payment_date(self):
        value = self.cleaned_data["payment_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("Payment date cannot be in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        case = self._case()
        amount = cleaned.get("amount")
        if case is not None and amount:
            paid_elsewhere = sum(
                p.amount for p in case.payments.all() if p.pk != self.instance.pk
            )
            remaining = case.fee - paid_elsewhere
            if amount > remaining:
                self.add_error("amount", f"Only {remaining:,.2f} is outstanding on this case.")
        return cleaned


class FollowUpForm(StyledModelForm):
    class Meta:
        model = PaymentFollowUp
        fields = ["followup_date", "method", "contact_person", "promised_payment_date", "notes"]
        widgets = {
            "followup_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "promised_payment_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "What did the hospital say?"}),
        }
