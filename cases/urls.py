from django.urls import path

from . import views

app_name = "cases"

urlpatterns = [
    path("", views.case_list, name="list"),
    path("add/", views.case_add, name="add"),
    path("import/", views.import_cases, name="import"),
    path("import/template/", views.import_template, name="import_template"),
    path("<int:pk>/", views.case_detail, name="detail"),
    path("<int:pk>/edit/", views.case_edit, name="edit"),
    path("<int:pk>/delete/", views.case_delete, name="delete"),
]
