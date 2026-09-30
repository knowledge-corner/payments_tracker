import logging

from django.contrib import messages
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.templatetags.static import static
from django.views.decorators.cache import cache_control, never_cache

from .forms import AppSettingsForm
from .models import AppSettings
from .permissions import admin_required

logger = logging.getLogger(__name__)

# Bump when static assets change so installed PWAs refresh their cache.
SW_CACHE_VERSION = "v3"


@cache_control(max_age=3600)
def manifest(request):
    data = {
        "name": "Anaesthesia Payments Tracker",
        "short_name": "Payments",
        "description": "Track completed anaesthesia cases, payments and follow-ups.",
        "id": "/",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f5f3fa",
        "theme_color": "#1e1b4b",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Add Case", "url": "/cases/add/", "icons": [{"src": static("icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Record Payment", "url": "/payments/record/", "icons": [{"src": static("icons/icon-192.png"), "sizes": "192x192"}]},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@never_cache
def service_worker(request):
    precache = [
        "/offline/",
        static("vendor/bootstrap/bootstrap.min.css"),
        static("vendor/bootstrap/bootstrap.bundle.min.js"),
        static("vendor/bootstrap-icons/bootstrap-icons.min.css"),
        static("vendor/bootstrap-icons/fonts/bootstrap-icons.woff2"),
        static("css/app.css"),
        static("js/app.js"),
        static("js/searchable-select.js"),
        static("icons/icon-192.png"),
    ]
    response = render(
        request, "pwa/sw.js", {"version": SW_CACHE_VERSION, "precache": precache},
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "pwa/offline.html")


@never_cache
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    # The Windows launcher looks for this exact text to confirm it reached *this* app.
    return HttpResponse("payments-tracker ok", content_type="text/plain")


@admin_required
def settings_view(request):
    obj = AppSettings.load()
    form = AppSettingsForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("app_settings")
    return render(request, "core/settings.html", {"form": form})


def csrf_failure(request, reason=""):
    """Friendly replacement for Django's bare "403 CSRF verification failed" page.

    On phones this mostly happens when a sign-in page was left open for a long
    time, or when the link was opened inside WhatsApp/Gmail's built-in browser.
    """
    logger.warning("CSRF failure on %s: %s (UA: %s)", request.path, reason, request.META.get("HTTP_USER_AGENT", "")[:120])
    if request.path == reverse("login"):
        messages.warning(
            request,
            "Your sign-in page had expired - please sign in again. If this keeps happening, open the "
            "link in Chrome or Safari (not inside WhatsApp/Gmail) and make sure cookies are allowed.",
        )
        return redirect("login")
    return render(request, "403_csrf.html", {"retry_url": request.path}, status=403)
