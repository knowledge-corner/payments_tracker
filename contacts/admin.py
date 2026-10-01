from django.contrib import admin

from .models import Contact, ContactAffiliation


class AffiliationInline(admin.TabularInline):
    model = ContactAffiliation
    extra = 0
    raw_id_fields = ["hospital"]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["name", "doctor", "role", "phone", "is_active"]
    list_filter = ["role", "is_active", "doctor"]
    search_fields = ["name", "phone"]
    inlines = [AffiliationInline]
