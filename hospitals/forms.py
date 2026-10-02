from django import forms

from core.forms import StyledForm, StyledModelForm

from .models import Hospital

CITY_SUGGESTIONS = ["Pune", "Pimpri-Chinchwad", "Mumbai", "Thane", "Navi Mumbai"]


class HospitalForm(StyledModelForm):
    """Add a hospital (saved straight away - no approval or duplicate check) or edit one."""

    class Meta:
        model = Hospital
        fields = ["name", "area", "city", "category", "address", "pincode", "phone"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}),
            "pincode": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 6}),
            "city": forms.TextInput(attrs={"list": "city-options"}),
        }

class AdminHospitalForm(HospitalForm):
    class Meta(HospitalForm.Meta):
        fields = ["name", "aliases", "area", "city", "district", "category", "ownership", "address", "pincode",
                  "phone", "email", "website", "is_active"]


class DirectoryImportForm(StyledForm):
    file = forms.FileField(
        label="Hospital directory file (.csv or .xlsx)",
        help_text="The 'Hospital Directory (National Health Portal)' CSV from data.gov.in, or any sheet with "
                  "hospital name / district / address columns.",
    )
    districts = forms.CharField(
        initial="Pune, Mumbai, Mumbai Suburban", max_length=300,
        help_text="Only rows from these districts/cities are imported (comma separated).",
    )
