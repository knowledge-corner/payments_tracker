from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from core.forms import StyledModelForm

from .models import Doctor, User


class DoctorForm(StyledModelForm):
    """Create/edit a doctor together with their login."""

    username = forms.CharField(max_length=150, help_text="Used to sign in, e.g. dr.mehta")
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False), required=False,
        help_text="Required for a new doctor. Leave blank to keep the current password.",
    )

    class Meta:
        model = Doctor
        fields = ["display_name", "phone", "registration_no", "specialisation", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["username"].initial = self.instance.user.username
            self.fields["email"].initial = self.instance.user.email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if not self.instance.pk and not password:
            self.add_error("password", "Set a password for the new doctor.")
        elif password:
            try:
                validate_password(password)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        doctor = super().save(commit=False)
        user = doctor.user if doctor.pk else User(role=User.ROLE_DOCTOR)
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.is_active = doctor.is_active
        name = doctor.display_name.replace("Dr.", "").replace("Dr ", "").strip()
        user.first_name, _, user.last_name = name.partition(" ")
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        doctor.user = user
        doctor.save()
        return doctor
