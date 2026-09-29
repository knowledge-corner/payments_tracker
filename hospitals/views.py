from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import scoped_cases

from .forms import HospitalForm
from .models import Hospital


@login_required
def hospital_list(request):
    q = request.GET.get("q", "").strip()
    show = request.GET.get("show", "active")
    hospitals = Hospital.objects.all()
    if show == "active":
        hospitals = hospitals.filter(is_active=True)
    if q:
        hospitals = hospitals.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(contact_person__icontains=q))

    # Open cases and outstanding per hospital, limited to cases the user can see.
    counts, totals = {}, {}
    for case in scoped_cases(request).outstanding().only("id", "hospital_id", "fee"):
        counts[case.hospital_id] = counts.get(case.hospital_id, 0) + 1
        totals[case.hospital_id] = totals.get(case.hospital_id, 0) + case.outstanding

    hospitals = list(hospitals)
    for h in hospitals:
        h.open_cases = counts.get(h.pk, 0)
        h.outstanding_total = totals.get(h.pk, 0)
    return render(request, "hospitals/hospital_list.html", {"hospitals": hospitals, "q": q, "show": show})


@login_required
def hospital_detail(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    cases = scoped_cases(request).filter(hospital=hospital).with_totals().select_related("doctor")
    open_cases = [c for c in cases if c.outstanding > 0]
    context = {
        "hospital": hospital,
        "recent_cases": cases[:10],
        "open_cases": open_cases,
        "outstanding_total": sum(c.outstanding for c in open_cases),
        "case_count": cases.count(),
    }
    return render(request, "hospitals/hospital_detail.html", context)


@login_required
def hospital_form(request, pk=None):
    hospital = get_object_or_404(Hospital, pk=pk) if pk else None
    form = HospitalForm(request.POST or None, instance=hospital)
    if not request.user.is_app_admin:
        # Doctors can add/edit hospitals but only admins can deactivate them.
        form.fields.pop("is_active")
    if request.method == "POST" and form.is_valid():
        hospital = form.save()
        messages.success(request, f"{hospital} saved.")
        next_url = request.GET.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(f"{next_url}?hospital={hospital.pk}")
        return redirect("hospitals:detail", pk=hospital.pk)
    return render(request, "hospitals/hospital_form.html", {"form": form, "hospital": hospital})
