from django.contrib import admin

from .models import NotificationPreference, PushSubscription, SentNotification


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "device", "created_at", "last_success_at", "failure_count"]
    search_fields = ["user__username"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "push_enabled", "daily_summary", "followup_reminders", "overdue_alerts",
                    "weekly_report", "payment_updates", "summary_hour"]


@admin.register(SentNotification)
class SentNotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "kind", "title", "devices"]
    list_filter = ["kind"]
