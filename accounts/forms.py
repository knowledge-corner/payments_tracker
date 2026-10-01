import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
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


def doctor_title(name):
    """'anjali mehta' -> 'Dr. Anjali Mehta' (keeps an existing Dr prefix)."""
    name = " ".join(name.split())
    if name[:3].lower() in ("dr.", "dr ") or name.lower() == "dr":
        name = name[3:].strip()
    return "Dr. " + " ".join(part[:1].upper() + part[1:] for part in name.split(" "))


class SignupForm(forms.Form):
    full_name = forms.CharField(
        label="Full name", max_length=110,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "e.g. Anjali Mehta"}),
        help_text="Shown as 'Dr. <name>' in the app.",
    )
    phone = forms.CharField(
        label="Mobile number", max_length=20,
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel", "placeholder": "+91 98xxxxxxxx"}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    registration_no = forms.CharField(label="Medical registration no. (optional)", max_length=50, required=False)
    username = forms.RegexField(
        regex=r"^[\w.@+-]+$", max_length=150,
        error_messages={"invalid": "Use letters, numbers and . @ + - _ only (no spaces)."},
        widget=forms.TextInput(attrs={"autocomplete": "username", "autocapitalize": "none", "placeholder": "e.g. dr.anjali"}),
        help_text="You will use this to sign in.",
    )
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text="At least 8 characters; not only numbers.")
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    agree = forms.BooleanField(
        label="I understand this app tracks work and payments only - no clinical or patient medical records.",
    )
    # Honeypot: real people never see or fill this field; simple bots do.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken - please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try signing in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise forms.ValidationError("Sign-up could not be completed.")
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        elif p1:
            candidate = User(username=cleaned.get("username", ""), email=cleaned.get("email", ""),
                             first_name=cleaned.get("full_name", ""))
            try:
                validate_password(p1, candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self, active=True):
        data = self.cleaned_data
        display = doctor_title(data["full_name"])
        first, _, last = display[4:].partition(" ")
        user = User(username=data["username"], email=data["email"], first_name=first, last_name=last,
                    role=User.ROLE_DOCTOR, is_active=active)
        user.set_password(data["password1"])
        user.save()
        return Doctor.objects.create(
            user=user, display_name=display, phone=data["phone"].strip(),
            registration_no=data.get("registration_no", "").strip(), is_active=active,
        )


class LoginForm(AuthenticationForm):
    """Adds a clear message for accounts waiting for admin approval."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Username or password is incorrect.",
        "pending": "Your account is waiting for admin approval. You can sign in once it has been activated.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "autocapitalize": "none", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "form-control"})

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            username, password = self.cleaned_data.get("username"), self.cleaned_data.get("password")
            user = User.objects.filter(username__iexact=username or "").first()
            if user and not user.is_active and password and user.check_password(password):
                raise forms.ValidationError(self.error_messages["pending"], code="pending")
            raise


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


def _mobile_digits(value):
    """Last 10 digits, so '+91 98220 12345', '098220-12345' and '9822012345' all match."""
    return re.sub(r"\D", "", value or "")[-10:]


class ForgotPasswordForm(forms.Form):
    """Step 1 of 'Forgot password': username + registered mobile + registered email must all match."""

    username = forms.CharField(max_length=150, widget=forms.TextInput(
        attrs={"autocomplete": "username", "autocapitalize": "none", "autofocus": True}))
    mobile = forms.CharField(label="Registered mobile number", max_length=20, widget=forms.TextInput(
        attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel", "placeholder": "+91 98xxxxxxxx"}))
    email = forms.EmailField(label="Registered email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    error_message = "These details don't match our records. Check the username, mobile number and email."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.user = None

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        user = User.objects.filter(username__iexact=cleaned["username"].strip()).first()
        doctor = getattr(user, "doctor_profile", None) if user else None
        mobile = _mobile_digits(cleaned["mobile"])
        if (
            user is None or doctor is None or len(mobile) < 10
            or _mobile_digits(doctor.phone) != mobile
            or not user.email or user.email.strip().lower() != cleaned["email"].strip().lower()
        ):
            raise forms.ValidationError(self.error_message, code="no_match")
        self.user = user
        return cleaned
