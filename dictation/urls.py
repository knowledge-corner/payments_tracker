from django.urls import path

from . import views

app_name = "dictation"

urlpatterns = [
    path("parse/", views.parse_view, name="parse"),
]
