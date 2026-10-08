from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.settings_page, name="settings"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("unsubscribe/", views.unsubscribe, name="unsubscribe"),
    path("test/", views.send_test, name="test"),
    path("key/", views.vapid_public_key, name="key"),
    path("cron/<str:token>/", views.cron_run, name="cron"),
]
