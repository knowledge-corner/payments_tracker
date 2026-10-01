import time

from django.contrib import messages
from django.contrib.auth import login
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from core.models import AppSettings
from core.permissions import admin_required

from .forms import DoctorForm, ForgotPasswordForm, SignupForm, StyledSetPasswordForm
from .models import Doctor, User


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


# --------------------------------------------------------------------------- #
# Forgot password: verify username + mobile + email, then set a new password
# on the spot (no email or OTP).
# --------------------------------------------------------------------------- #

RESET_SESSION_KEY = "pw_reset"
RESET_WINDOW_SECONDS = 10 * 60      # time allowed to set the new password after verifying
MAX_ATTEMPTS, LOCK_SECONDS = 5, 15 * 60


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


@never_cache
def forgot_password(request):
    attempts_key = f"pw-reset-attempts:{_client_ip(request)}"
    attempts = cache.get(attempts_key, 0)
    locked = attempts >= MAX_ATTEMPTS
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and not locked:
        if form.is_valid():
            cache.delete(attempts_key)
            request.session[RESET_SESSION_KEY] = {"uid": form.user.pk, "at": time.time()}
            return redirect("password_reset_new")
        cache.set(attempts_key, attempts + 1, LOCK_SECONDS)
        locked = attempts + 1 >= MAX_ATTEMPTS
    return render(request, "registration/forgot_password.html", {"form": form, "locked": locked})


@never_cache
def set_new_password(request):
    data = request.session.get(RESET_SESSION_KEY) or {}
    user = User.objects.filter(pk=data.get("uid")).first()
    if user is None or time.time() - data.get("at", 0) > RESET_WINDOW_SECONDS:
        request.session.pop(RESET_SESSION_KEY, None)
        messages.warning(request, "Please verify your details again.")
        return redirect("password_reset")
    form = StyledSetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.session.pop(RESET_SESSION_KEY, None)
        messages.success(request, "Password changed. Sign in with your new password.")
        return redirect("login")
    return render(request, "registration/set_new_password.html", {"form": form, "reset_user": user})
