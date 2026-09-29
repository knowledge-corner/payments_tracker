from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from accounts.models import Doctor


def admin_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_app_admin:
            raise PermissionDenied("Only administrators can do this.")
        return view(request, *args, **kwargs)

    return wrapper


def visible_doctors(user):
    if user.is_app_admin:
        return Doctor.objects.filter(is_active=True)
    return Doctor.objects.filter(user=user)


def selected_doctor(request):
    """Admins can filter any page by ?doctor=<id>; doctors always see only themselves."""
    if request.user.is_app_admin:
        doctor_id = request.GET.get("doctor")
        if doctor_id and doctor_id.isdigit():
            return Doctor.objects.filter(pk=doctor_id).first()
        return None
    return request.user.doctor_profile


def require_doctor_profile(view):
    """Doctor accounts must be linked to a Doctor record before recording work."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_app_admin and request.user.doctor_profile is None:
            messages.error(request, "Your login is not linked to a doctor profile yet. Please contact the admin.")
            return redirect("dashboard:home")
        return view(request, *args, **kwargs)

    return wrapper


def scoped_cases(request):
    """Cases the current user may see, narrowed by the admin's doctor filter if set."""
    from cases.models import Case

    qs = Case.objects.for_user(request.user)
    if request.user.is_app_admin:
        doctor = selected_doctor(request)
        if doctor:
            qs = qs.filter(doctor=doctor)
    return qs
