from django import forms
from django.utils import timezone

from core.forms import StyledModelForm
from hospitals.models import Department, Hospital

from .models import Contact, ContactAffiliation


class ContactForm(StyledModelForm):
    class Meta:
        model = Contact
        fields = ["name", "role", "phone", "alt_phone", "email", "notes", "is_active"]
        widgets = {
            "phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "off"}),
            "alt_phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "off"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("phone") and not cleaned.get("alt_phone"):
            self.add_error("phone", "Enter a phone number so the call button works.")
        return cleaned


class AffiliationForm(StyledModelForm):
    """Add 'works at' - hospital is picked with the type-to-search box."""

    moved_from_others = forms.BooleanField(
        required=False, label="They moved here - end their other current hospitals",
    )

    class Meta:
        model = ContactAffiliation
        fields = ["hospital", "department", "is_primary", "start_date"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hospital_field = self.fields["hospital"]
        hospital_field.queryset = Hospital.objects.active()
        selected = self.data.get(self.add_prefix("hospital")) or self.initial.get("hospital")
        choices = [("", "Search hospital")]
        if selected:
            h = Hospital.objects.filter(pk=selected).first()
            if h:
                choices.append((h.pk, h.label))
        hospital_field.widget.choices = choices
        hospital_field.widget.attrs.update({
            "data-searchable": "", "data-search-url": "/hospitals/search/", "data-placeholder": "Type to search hospital",
        })
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["department"].empty_label = "All departments"
        self.fields["start_date"].initial = timezone.localdate()
