from django.conf import settings
from django.db import models


class NotificationKind:
    DAILY_SUMMARY = "daily_summary"
    FOLLOWUP = "followup_reminders"
    OVERDUE = "overdue_alerts"
    WEEKLY = "weekly_report"
    PAYMENT = "payment_updates"
    TEST = "test"

    # (field on NotificationPreference, label, description)
    CHOICES = [
        (DAILY_SUMMARY, "Morning summary", "Each morning: follow-ups due today, overdue amount and total outstanding."),
        (FOLLOWUP, "Follow-up reminders", "When unpaid cases reach a reminder day (e.g. 7, 14, 21 days)."),
        (OVERDUE, "Overdue alerts", "When a case passes its payment due date."),
        (WEEKLY, "Weekly report", "Monday morning: last week's cases, billing and payments received."),
        (PAYMENT, "Payment updates", "When someone else (e.g. the admin) records a payment on your case."),
    ]
    LABELS = dict((k, label) for k, label, _ in CHOICES)


class PushSubscription(models.Model):
    """One browser/device that agreed to receive push notifications."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    device = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    failure_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.device or 'device'}"


class NotificationPreference(models.Model):
    HOUR_CHOICES = [(h, f"{h % 12 or 12}:00 {'AM' if h < 12 else 'PM'}") for h in range(5, 23)]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_prefs")
    push_enabled = models.BooleanField("Push notifications", default=True)
    daily_summary = models.BooleanField(default=True)
    followup_reminders = models.BooleanField(default=True)
    overdue_alerts = models.BooleanField(default=True)
    weekly_report = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    summary_hour = models.PositiveSmallIntegerField(
        "Morning summary time", choices=HOUR_CHOICES, default=9,
        help_text="Also the time for follow-up reminders, overdue alerts and the weekly report.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification settings for {self.user}"

    @classmethod
    def for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def wants(self, kind):
        if kind == NotificationKind.TEST:
            return True
        return self.push_enabled and getattr(self, kind, False)


class SentNotification(models.Model):
    """History of notifications sent (shown on the settings page) and de-duplication."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_notifications")
    kind = models.CharField(max_length=30)
    key = models.CharField(max_length=120, help_text="De-duplication key, e.g. daily:2026-09-30")
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=300)
    url = models.CharField(max_length=200, default="/")
    devices = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="unique_notification_key_per_user")]

    @property
    def kind_label(self):
        return NotificationKind.LABELS.get(self.kind, "Test")


class NotifiedCase(models.Model):
    """Remembers which case events were already notified (per reminder date / overdue)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    key = models.CharField(max_length=80)  # e.g. followup:123:2026-09-30, overdue:123
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="unique_notified_case_key")]
