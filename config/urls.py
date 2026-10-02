from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as account_views
from accounts.forms import LoginForm
from core import views as core_views

admin.site.site_header = "Payments Tracker Admin"
admin.site.site_title = "Payments Tracker"
# /admin/ is the raw database panel: developer (superuser) only. App admins never
# get in, and the app does not link to it.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", redirect_authenticated_user=True, authentication_form=LoginForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", account_views.signup, name="signup"),
    # Forgot password / user ID: verified with the registered mobile number (no email needed)
    path("password-reset/", account_views.forgot_password, name="password_reset"),
    path("password-reset/new/", account_views.set_new_password, name="password_reset_new"),
    path("forgot-user-id/", account_views.forgot_username, name="forgot_username"),
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
