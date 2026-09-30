from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render

from core.models import AppSettings
from core.permissions import admin_required

from .forms import DoctorForm, SignupForm
from .models import Doctor


@admin_required
def doctor_list(request):
    doctors = Doctor.objects.select_related("user").order_by("is_active", "-created_at")
    return render(request, "accounts/doctor_list.html", {"doctors": doctors})


@admin_required
def doctor_form(request, pk=None):
    doctor = get_object_or_404(Doctor, pk=pk) if pk else None
    form = DoctorForm(request.POST or None, instance=doctor)
    if request.method == "POST" and form.is_valid():
        doctor = form.save()
        messages.success(request, f"{doctor} saved.")
        return redirect("accounts:doctor_list")
    return render(request, "accounts/doctor_form.html", {"form": form, "doctor": doctor})


def signup(request):
    """Self-registration for doctors (can be switched off or require approval in Settings)."""
    settings_obj = AppSettings.load()
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    if not settings_obj.allow_signups:
        messages.info(request, "New sign-ups are closed. Please ask the administrator to create your account.")
        return redirect("login")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        needs_approval = settings_obj.signup_requires_approval
        doctor = form.save(active=not needs_approval)
        if needs_approval:
            messages.success(
                request,
                f"Thank you, {doctor}. Your account has been created and is waiting for admin approval. "
                "You can sign in once it has been activated.",
            )
            return redirect("login")
        login(request, doctor.user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome, {doctor}! Start by adding a case or importing your Excel sheet.")
        return redirect("dashboard:home")
    return render(request, "registration/signup.html", {"form": form, "needs_approval": settings_obj.signup_requires_approval})
