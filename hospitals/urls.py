from django.urls import path

from . import views

app_name = "hospitals"

urlpatterns = [
    path("", views.hospital_list, name="list"),
    path("search/", views.hospital_search, name="search"),
    path("add/", views.hospital_add, name="add"),
    path("directory/import/", views.directory_import, name="directory_import"),
    path("<int:pk>/", views.hospital_detail, name="detail"),
    path("<int:pk>/edit/", views.hospital_edit, name="edit"),
]
