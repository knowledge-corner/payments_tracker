from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as account_views
from accounts.forms import LoginForm, StyledSetPasswordForm
from core import views as core_views

admin.site.site_header = "Payments Tracker Admin"
admin.site.site_title = "Payments Tracker"

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
    # Forgot password (email link)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html", form_class=StyledSetPasswordForm),
        name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
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
