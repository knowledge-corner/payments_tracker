from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.doctor_list, name="doctor_list"),
    path("add/", views.doctor_form, name="doctor_add"),
    path("<int:pk>/edit/", views.doctor_form, name="doctor_edit"),
]
