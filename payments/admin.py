from django.contrib import admin

from .models import Payment, PaymentFollowUp


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["payment_date", "case", "amount", "mode", "reference_no", "source"]
    list_filter = ["mode", "source", "case__doctor", "case__hospital"]
    search_fields = ["reference_no", "case__patient_reference", "case__hospital__name", "legacy_ref"]
    date_hierarchy = "payment_date"
    raw_id_fields = ["case"]


@admin.register(PaymentFollowUp)
class PaymentFollowUpAdmin(admin.ModelAdmin):
    list_display = ["followup_date", "case", "method", "contact_person", "promised_payment_date"]
    list_filter = ["method", "case__doctor"]
    raw_id_fields = ["case"]
