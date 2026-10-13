from django import forms

from core.forms import StyledModelForm

from .models import Doctor


class DoctorForm(StyledModelForm):
    """An anaesthetist of the practice (no personal login needed)."""

    class Meta:
        model = Doctor
        fields = ["display_name", "phone", "registration_no", "specialisation", "is_active"]
        widgets = {"phone": forms.TextInput(attrs={"type": "tel", "inputmode": "tel"})}

    def clean_display_name(self):
        name = doctor_title(self.cleaned_data["display_name"])
        qs = Doctor.objects.filter(display_name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An anaesthetist with this name already exists.")
        return name


def doctor_title(name):
    """'anjali mehta' -> 'Dr. Anjali Mehta' (keeps an existing Dr prefix)."""
    name = " ".join(name.split())
    if name[:3].lower() in ("dr.", "dr ") or name.lower() == "dr":
        name = name[3:].strip()
    return "Dr. " + " ".join(part[:1].upper() + part[1:] for part in name.split(" "))
