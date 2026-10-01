from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.contact_list, name="list"),
    path("add/", views.contact_add, name="add"),
    path("for-hospital/", views.for_hospital, name="for_hospital"),
    path("<int:pk>/", views.contact_detail, name="detail"),
    path("<int:pk>/edit/", views.contact_edit, name="edit"),
    path("<int:pk>/links/add/", views.link_add, name="link_add"),
    path("<int:pk>/links/<int:link_pk>/end/", views.link_end, name="link_end"),
    path("<int:pk>/links/<int:link_pk>/primary/", views.link_primary, name="link_primary"),
]
