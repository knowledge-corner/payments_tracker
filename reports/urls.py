from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.index, name="index"),
    path("cases/", views.cases_report, name="cases"),
    path("monthly/", views.monthly, name="monthly"),
    path("hospitals/", views.hospital_wise, name="hospitals"),
    path("payments/", views.payment_history, name="payments"),
]
