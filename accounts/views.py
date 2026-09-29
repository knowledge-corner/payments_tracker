from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import admin_required

from .forms import DoctorForm
from .models import Doctor


@admin_required
def doctor_list(request):
    doctors = Doctor.objects.select_related("user").order_by("-is_active", "display_name")
    return render(request, "accounts/doctor_list.html", {"doctors": doctors})


@admin_required
def doctor_form(request, pk=None):
    doctor = get_object_or_404(Doctor, pk=pk) if pk else None
    form = DoctorForm(request.POST or None, instance=doctor)
    if request.method == "POST" and form.is_valid():
        doctor = form.save()
        messages.success(request, f"{doctor} saved.")
        return redirect("accounts:doctor_list")
    return render(request, "accounts/doctor_form.html", {"form": form, "doctor": doctor})
