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
    path("surgeons/", views.surgeon_list, name="surgeon_list"),
    path("surgeons/add/", views.surgeon_add, name="surgeon_add"),
    path("surgeons/<int:pk>/", views.surgeon_detail, name="surgeon_detail"),
    path("surgeons/<int:pk>/edit/", views.surgeon_edit, name="surgeon_edit"),
    path("surgeons/<int:pk>/hospitals/add/", views.surgeon_link_add, name="surgeon_link_add"),
    path("surgeons/<int:pk>/hospitals/<int:link_pk>/remove/", views.surgeon_link_remove, name="surgeon_link_remove"),
]
