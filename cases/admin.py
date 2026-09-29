from django.contrib import admin

from payments.models import Payment, PaymentFollowUp

from .models import Case


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["amount", "payment_date", "mode", "reference_no", "notes"]


class FollowUpInline(admin.TabularInline):
    model = PaymentFollowUp
    extra = 0
    fields = ["followup_date", "method", "contact_person", "promised_payment_date", "notes"]


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ["case_date", "doctor", "hospital", "patient_reference", "procedure_type", "fee", "due_date", "source"]
    list_filter = ["doctor", "hospital", "source", "case_date"]
    search_fields = ["patient_reference", "procedure_type", "hospital__name", "legacy_ref"]
    date_hierarchy = "case_date"
    inlines = [PaymentInline, FollowUpInline]
