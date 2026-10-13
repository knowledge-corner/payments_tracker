import time

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.forms import doctor_title
from accounts.models import Doctor

from . import practice
from .models import AppSettings
from .permissions import admin_required

MAX_ATTEMPTS, LOCK_SECONDS = 8, 15 * 60


def _ip(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def _next(request, default="/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) and nxt.startswith("/"):
        return nxt
    return default


def _inside(request):
    user = request.user
    return practice.has_valid_code(request) or (user.is_authenticated and user.is_app_admin)


@never_cache
def enter(request):
    """Practice code screen (once per phone)."""
    code = practice.current_code()
    if practice.has_valid_code(request, code):
        return redirect(_next(request))
    key = f"practice-code-attempts:{_ip(request)}"
    attempts = cache.get(key, 0)
    locked = attempts >= MAX_ATTEMPTS
    error = ""
    if request.method == "POST" and code and not locked:
        typed = request.POST.get("code", "").strip()
        if typed and typed == code:
            cache.delete(key)
            login(request, practice.practice_user(), backend="django.contrib.auth.backends.ModelBackend")
            target = _next(request)
            if not practice.device_doctor(request) and request.COOKIES.get(practice.WHO_COOKIE) != "0":
                target = reverse("practice_who") + f"?next={target}"
            response = redirect(target)
            practice.remember_code(response, code)
            return response
        cache.set(key, attempts + 1, LOCK_SECONDS)
        locked = attempts + 1 >= MAX_ATTEMPTS
        time.sleep(0.5)
        error = "That code is not right. Ask a colleague for the practice code."
    return render(request, "practice/enter.html", {
        "code_set": bool(code), "locked": locked, "error": error, "next": _next(request, ""),
    })


@never_cache
def who(request):
    """'Who is using this phone?' - sets the default anaesthetist for this phone."""
    if not _inside(request):
        return redirect("practice_enter")
    doctors = Doctor.objects.filter(is_active=True)
    error = ""
    if request.method == "POST":
        choice = request.POST.get("doctor", "")
        name = " ".join(request.POST.get("new_name", "").split())
        doctor = None
        if name:
            title = doctor_title(name)
            doctor = Doctor.objects.filter(display_name__iexact=title).first() or Doctor.objects.create(
                display_name=title, phone=request.POST.get("new_phone", "").strip()[:20])
            value = str(doctor.pk)
        elif choice == "0":
            value = "0"
        elif choice.isdigit() and doctors.filter(pk=choice).exists():
            value = choice
        else:
            value = None
            error = "Choose your name, or add it."
        if value is not None:
            response = redirect(_next(request))
            response.set_cookie(practice.WHO_COOKIE, value, max_age=practice.COOKIE_AGE, samesite="Lax")
            return response
    current = request.COOKIES.get(practice.WHO_COOKIE, "")
    return render(request, "practice/who.html", {
        "doctors": doctors, "current": current, "error": error, "next": _next(request, ""),
    })


@require_POST
def lock(request):
    """'Lock this phone': forget the code on this phone."""
    logout(request)
    response = redirect("practice_enter")
    response.delete_cookie(practice.CODE_COOKIE)
    return response


@never_cache
def admin_login(request):
    """Administrator sign-in with own username + password (no practice code needed)."""
    error = ""
    key = f"practice-admin-attempts:{_ip(request)}"
    attempts = cache.get(key, 0)
    if request.method == "POST":
        if attempts >= MAX_ATTEMPTS:
            error = "Too many attempts. Please wait 15 minutes."
        else:
            user = authenticate(request, username=request.POST.get("username", "").strip(),
                                password=request.POST.get("password", ""))
            if user is not None and user.is_app_admin and not practice.is_practice_session(user):
                cache.delete(key)
                login(request, user)
                return redirect(_next(request, reverse("practice_settings")))
            cache.set(key, attempts + 1, LOCK_SECONDS)
            error = "Administrator username or password is not right."
    return render(request, "practice/admin_login.html", {"error": error, "next": _next(request, "")})


@admin_required
def practice_settings(request):
    """See / change the practice code (everyone inside, and administrators)."""
    settings_obj = AppSettings.load()
    error = ""
    if request.method == "POST":
        new = request.POST.get("new_code", "").strip()
        if len(new) < 4 or len(new) > 30 or " " in new:
            error = "Use at least 4 characters (letters or digits, no spaces)."
        elif new != request.POST.get("confirm_code", "").strip():
            error = "The two codes do not match."
        else:
            settings_obj.practice_code = new
            settings_obj.save(update_fields=["practice_code", "updated_at"])
            messages.success(request, "Practice code changed. Every other phone will ask for the new code.")
            response = redirect("practice_settings")
            if practice.is_practice_session(request.user):
                practice.remember_code(response, new)  # keep this phone signed in
            return response
    return render(request, "practice/settings.html", {"code": settings_obj.practice_code, "error": error})
