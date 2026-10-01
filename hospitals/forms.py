from django import forms

from core.forms import StyledForm, StyledModelForm

from .models import Hospital

CITY_SUGGESTIONS = ["Pune", "Pimpri-Chinchwad", "Mumbai", "Thane", "Navi Mumbai"]


class HospitalForm(StyledModelForm):
    """Add a hospital that is missing from the directory (doctors) or edit one (admins)."""

    confirm_new = forms.BooleanField(
        required=False, label="Yes, this is a different hospital - add it",
    )

    class Meta:
        model = Hospital
        fields = ["name", "area", "city", "category", "address", "pincode", "phone"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}),
            "pincode": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 6}),
            "city": forms.TextInput(attrs={"list": "city-options"}),
        }

    def __init__(self, *args, check_duplicates=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_duplicates = check_duplicates and not self.instance.pk
        self.similar = []
        if not self.check_duplicates:
            self.fields.pop("confirm_new")

    def clean(self):
        cleaned = super().clean()
        if self.check_duplicates and cleaned.get("name") and not cleaned.get("confirm_new"):
            probe = Hospital(name=cleaned["name"], city=cleaned.get("city", ""))
            self.similar = list(probe.similar())
            if self.similar:
                raise forms.ValidationError(
                    "Similar hospitals already exist. Pick one of them, or tick the box below if yours is different."
                )
        return cleaned


class AdminHospitalForm(HospitalForm):
    class Meta(HospitalForm.Meta):
        fields = ["name", "aliases", "area", "city", "district", "category", "ownership", "address", "pincode",
                  "phone", "email", "website", "verified", "is_active"]


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


class MergeForm(StyledForm):
    target = forms.ModelChoiceField(
        queryset=Hospital.objects.none(), label="Keep this hospital",
        help_text="All cases and contacts move to the hospital you keep; this entry is hidden.",
    )

    def __init__(self, *args, hospital=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Hospital.objects.active()
        if hospital is not None:
            qs = qs.exclude(pk=hospital.pk)
            self.fields["target"].queryset = qs
            similar = list(hospital.similar(limit=20))
            self.fields["target"].widget.choices = [("", "Select the hospital to keep")] + [(h.pk, h.label) for h in similar]
        self.fields["target"].widget.attrs.update({
            "data-searchable": "", "data-search-url": "/hospitals/search/", "data-placeholder": "Search hospital to keep",
        })
