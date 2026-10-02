from django.contrib import admin

from .models import Contact, ContactAffiliation, Surgeon, SurgeonHospital


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


class SurgeonHospitalInline(admin.TabularInline):
    model = SurgeonHospital
    extra = 0
    raw_id_fields = ["hospital"]


@admin.register(Surgeon)
class SurgeonAdmin(admin.ModelAdmin):
    list_display = ["name", "doctor", "phone", "speciality", "is_active"]
    list_filter = ["is_active", "doctor"]
    search_fields = ["name", "phone"]
    inlines = [SurgeonHospitalInline]
