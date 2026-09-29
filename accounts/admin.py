from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Doctor, User


class DoctorInline(admin.StackedInline):
    model = Doctor
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Role", {"fields": ("role",)}),)
    list_display = ["username", "first_name", "last_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    inlines = [DoctorInline]


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "phone", "registration_no", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["display_name", "user__username", "phone"]
