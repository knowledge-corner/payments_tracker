from django.contrib import admin

from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "contact_person", "contact_number", "default_fee", "payment_terms_days", "is_active"]
    list_filter = ["is_active", "city"]
    search_fields = ["name", "city", "contact_person"]
