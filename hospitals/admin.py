from django.contrib import admin

from .models import Department, Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "area", "city", "category", "source", "created_by", "is_active"]
    list_filter = ["city", "source", "is_active", "category"]
    search_fields = ["name", "aliases", "area", "pincode"]
    raw_id_fields = ["merged_into"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
