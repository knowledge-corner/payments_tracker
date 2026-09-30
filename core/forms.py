from django import forms

from .models import AppSettings


class BootstrapMixin:
    """Adds Bootstrap classes to every widget so templates stay simple."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class StyledForm(BootstrapMixin, forms.Form):
    pass


class StyledModelForm(BootstrapMixin, forms.ModelForm):
    pass


class AppSettingsForm(StyledModelForm):
    class Meta:
        model = AppSettings
        fields = [
            "practice_name", "default_payment_terms_days",
            "reminder_days", "repeat_reminder_every_days",
            "allow_signups", "signup_requires_approval",
        ]
