from core.forms import StyledModelForm

from .models import NotificationKind, NotificationPreference


class NotificationPreferenceForm(StyledModelForm):
    class Meta:
        model = NotificationPreference
        fields = ["push_enabled"] + [k for k, _, _ in NotificationKind.CHOICES] + ["summary_hour"]

    def kind_fields(self):
        return [(self[k], label, help_text) for k, label, help_text in NotificationKind.CHOICES]
