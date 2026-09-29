from django import forms

from core.forms import StyledModelForm

from .models import Hospital


class HospitalForm(StyledModelForm):
    class Meta:
        model = Hospital
        fields = [
            "name", "city", "address", "contact_person", "contact_number",
            "default_fee", "payment_terms_days", "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "contact_number": forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}),
            "default_fee": forms.NumberInput(attrs={"inputmode": "decimal", "step": "1"}),
        }
