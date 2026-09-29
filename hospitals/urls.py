from django.urls import path

from . import views

app_name = "hospitals"

urlpatterns = [
    path("", views.hospital_list, name="list"),
    path("add/", views.hospital_form, name="add"),
    path("<int:pk>/", views.hospital_detail, name="detail"),
    path("<int:pk>/edit/", views.hospital_form, name="edit"),
]
