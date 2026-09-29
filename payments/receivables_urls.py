from django.urls import path

from . import views

app_name = "receivables"

urlpatterns = [
    path("", views.receivables, name="list"),
]
