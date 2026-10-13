from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from core import practice_views
from core import views as core_views

admin.site.site_header = "Payments Tracker Admin"
admin.site.site_title = "Payments Tracker"
# /admin/ is the raw database panel: developer (superuser) only. App admins never
# get in, and the app does not link to it.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser

urlpatterns = [
    path("admin/", admin.site.urls),
    # Shared practice access: practice code once per phone; administrators sign in separately.
    path("practice/", practice_views.enter, name="practice_enter"),
    path("practice/who/", practice_views.who, name="practice_who"),
    path("practice/lock/", practice_views.lock, name="practice_lock"),
    path("practice/admin/", practice_views.admin_login, name="practice_admin_login"),
    path("settings/practice/", practice_views.practice_settings, name="practice_settings"),
    path("login/", RedirectView.as_view(pattern_name="practice_enter", query_string=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # PWA + infrastructure
    path("manifest.webmanifest", core_views.manifest, name="manifest"),
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("offline/", core_views.offline, name="offline"),
    path("health/", core_views.health, name="health"),
    path("settings/", core_views.settings_view, name="app_settings"),
    # Feature modules
    path("", include("dashboard.urls")),
    path("hospitals/", include("hospitals.urls")),
    path("cases/", include("cases.urls")),
    path("payments/", include("payments.urls")),
    path("receivables/", include("payments.receivables_urls")),
    path("reports/", include("reports.urls")),
    path("doctors/", include("accounts.urls")),
    path("contacts/", include("contacts.urls")),
    path("notifications/", include("notifications.urls")),
]
