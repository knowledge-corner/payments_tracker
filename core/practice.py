"""
Shared practice access (organisation level, no personal logins).

* Each phone enters the practice code once; a signed cookie remembers it with no
  expiry in practice (10 years, renewed on every visit). Changing the code in
  Practice settings makes every remembered phone ask for the new code.
* After the code, the phone says who is using it ("pt_who" cookie): the default
  anaesthetist for new cases and for this phone's reminders.
* Everybody inside acts as the shared "practice" user, which has admin rights:
  all cases, all anaesthetists, add / edit / delete anything.
* Administrators can still sign in with their own username and password (no code
  needed) - that is the way to see or reset the code if nobody remembers it.
"""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import redirect
from django.urls import reverse

PRACTICE_USERNAME = "practice"
CODE_COOKIE = "pt_practice"
WHO_COOKIE = "pt_who"
DEVICE_COOKIE = "pt_device"
COOKIE_AGE = 60 * 60 * 24 * 365 * 10  # "forever"

EXEMPT_PREFIXES = (
    "/practice/", "/static/", "/media/", "/sw.js", "/manifest.webmanifest", "/offline/", "/health/",
    "/admin/", "/notifications/cron/", "/favicon",
)


def current_code():
    from .models import AppSettings

    return AppSettings.load().practice_code


def fingerprint(code):
    return hmac.new(settings.SECRET_KEY.encode(), f"practice:{code}".encode(), hashlib.sha256).hexdigest()[:24]


def practice_user():
    from accounts.models import User

    user, created = User.objects.get_or_create(
        username=PRACTICE_USERNAME,
        defaults={"role": User.ROLE_ADMIN, "first_name": "Practice", "is_active": True},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def remember_code(response, code):
    response.set_signed_cookie(CODE_COOKIE, fingerprint(code), salt=CODE_COOKIE, max_age=COOKIE_AGE,
                               httponly=True, samesite="Lax", secure=settings.SESSION_COOKIE_SECURE)


def has_valid_code(request, code=None):
    code = current_code() if code is None else code
    if not code:
        return False
    value = request.get_signed_cookie(CODE_COOKIE, default=None, salt=CODE_COOKIE)
    return bool(value) and hmac.compare_digest(value, fingerprint(code))


def device_key(request):
    return request.COOKIES.get(DEVICE_COOKIE, "")


def device_doctor(request):
    """The anaesthetist this phone said it belongs to (or None)."""
    from accounts.models import Doctor

    value = request.COOKIES.get(WHO_COOKIE, "")
    if value.isdigit():
        return Doctor.objects.filter(pk=int(value), is_active=True).first()
    return None


def is_practice_session(user):
    return user.is_authenticated and user.username == PRACTICE_USERNAME


class PracticeAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        new_device = None
        if not request.COOKIES.get(DEVICE_COOKIE):
            # Give the phone its key now, so this very request (e.g. turning on notifications) can use it.
            new_device = request.COOKIES[DEVICE_COOKIE] = secrets.token_hex(12)
        response = self._check(request)
        if response is None:
            response = self.get_response(request)
            renew = getattr(request, "_renew_practice_cookie", None)
            if renew and CODE_COOKIE not in response.cookies and renew == current_code():  # view may have set a new code
                remember_code(response, renew)
        if new_device:
            response.set_cookie(DEVICE_COOKIE, new_device, max_age=COOKIE_AGE, httponly=True,
                                samesite="Lax", secure=settings.SESSION_COOKIE_SECURE)
        return response

    def _check(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return None
        user = request.user
        # Administrators signed in with their own password do not need the code.
        if user.is_authenticated and user.is_app_admin and not is_practice_session(user):
            return None
        code = current_code()
        if code and has_valid_code(request, code):
            if not is_practice_session(user):
                login(request, practice_user(), backend="django.contrib.auth.backends.ModelBackend")
            request._renew_practice_cookie = code
            return None
        if user.is_authenticated:
            logout(request)
        target = reverse("practice_enter")
        if request.method == "GET" and request.path != "/":
            target += f"?next={request.get_full_path()}"
        return redirect(target)
