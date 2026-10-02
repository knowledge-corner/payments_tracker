from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from contacts.models import ContactAffiliation
from core.permissions import admin_required, scoped_cases

from .directory import import_directory
from .forms import CITY_SUGGESTIONS, AdminHospitalForm, DirectoryImportForm, HospitalForm
from .models import Hospital


def my_hospital_ids(request):
    """Hospitals the user works with: hospitals of their cases + where their contacts work."""
    ids = set(scoped_cases(request).values_list("hospital_id", flat=True).distinct())
    links = ContactAffiliation.objects.current()
    if not request.user.is_app_admin:
        links = links.filter(contact__doctor__user=request.user)
    ids.update(links.values_list("hospital_id", flat=True))
    return ids


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None


@login_required
def hospital_list(request):
    q = request.GET.get("q", "").strip()
    mine = my_hospital_ids(request)
    # Outstanding per hospital for the user's own cases.
    counts, totals = {}, {}
    for case in scoped_cases(request).outstanding().only("id", "hospital_id", "fee"):
        counts[case.hospital_id] = counts.get(case.hospital_id, 0) + 1
        totals[case.hospital_id] = totals.get(case.hospital_id, 0) + case.outstanding

    if q:
        results = list(Hospital.objects.active().search(q).order_by("name")[:60])
        results.sort(key=lambda h: (h.pk not in mine, h.name.lower()))
    else:
        last_case = {
            r["hospital_id"]: r["last"]
            for r in scoped_cases(request).values("hospital_id").annotate(last=Max("case_date")).order_by()
        }
        results = list(Hospital.objects.filter(pk__in=mine))
        results.sort(key=lambda h: (-(totals.get(h.pk) or 0), h.name.lower()))
        for h in results:
            h.last_case = last_case.get(h.pk)
    for h in results:
        h.is_mine = h.pk in mine
        h.open_cases = counts.get(h.pk, 0)
        h.outstanding_total = totals.get(h.pk, 0)
    return render(request, "hospitals/hospital_list.html", {
        "hospitals": results, "q": q, "directory_size": Hospital.objects.active().count(),
    })


@login_required
def hospital_search(request):
    """JSON for the type-to-search hospital picker: user's hospitals first."""
    q = request.GET.get("q", "").strip()
    mine = my_hospital_ids(request)
    if q:
        qs = list(Hospital.objects.active().search(q).order_by("name")[:40])
    else:
        qs = list(Hospital.objects.filter(pk__in=mine, is_active=True))
    qs.sort(key=lambda h: (h.pk not in mine, h.name.lower()))
    return JsonResponse({"results": [
        {"id": h.pk, "label": h.name, "sub": h.place, "mine": h.pk in mine} for h in qs[:20]
    ]})


@login_required
def hospital_detail(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    if hospital.merged_into_id:
        return redirect(hospital.merged_into)
    cases = scoped_cases(request).filter(hospital=hospital).with_totals().select_related("doctor", "surgeon")
    open_cases = [c for c in cases if c.outstanding > 0]
    links = hospital.contact_links.select_related("contact").order_by("end_date", "-is_primary")
    if not request.user.is_app_admin:
        links = links.filter(contact__doctor__user=request.user)
    return render(request, "hospitals/hospital_detail.html", {
        "hospital": hospital,
        "recent_cases": cases[:10],
        "open_cases": open_cases,
        "outstanding_total": sum(c.outstanding for c in open_cases),
        "case_count": cases.count(),
        "current_links": [link for link in links if link.is_current],
        "past_links": [link for link in links if not link.is_current],
        "can_edit": _can_edit(request.user, hospital),
    })


def _can_edit(user, hospital):
    if user.is_app_admin:
        return True
    return hospital.created_by_id == user.pk


@login_required
def hospital_add(request):
    is_admin = request.user.is_app_admin
    form_class = AdminHospitalForm if is_admin else HospitalForm
    initial = {"name": request.GET.get("name", ""), "city": request.GET.get("city", "")}
    form = form_class(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        hospital = form.save(commit=False)
        hospital.source = "admin" if is_admin else "doctor"
        hospital.created_by = request.user
        hospital.verified = True
        hospital.save()
        messages.success(request, f"{hospital} added to the hospital list.")
        nxt = _safe_next(request)
        if nxt:
            sep = "&" if "?" in nxt else "?"
            return redirect(f"{nxt}{sep}hospital={hospital.pk}")
        return redirect(hospital)
    return render(request, "hospitals/hospital_form.html", {
        "form": form, "hospital": None, "cities": CITY_SUGGESTIONS, "next": _safe_next(request) or "",
    })


@login_required
def hospital_edit(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    if not _can_edit(request.user, hospital):
        raise PermissionDenied
    form_class = AdminHospitalForm if request.user.is_app_admin else HospitalForm
    form = form_class(request.POST or None, instance=hospital)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hospital updated.")
        return redirect(hospital)
    return render(request, "hospitals/hospital_form.html", {"form": form, "hospital": hospital, "cities": CITY_SUGGESTIONS})


@admin_required
def directory_import(request):
    form = DirectoryImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            counts = import_directory(form.cleaned_data["file"], form.cleaned_data["districts"].split(","))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Imported: {counts['created']} new and {counts['updated']} updated hospitals "
                f"({counts['matched']} rows matched the districts; {counts['skipped_system']} non-allopathic skipped).",
            )
            return redirect("hospitals:list")
    stats = {s: Hospital.objects.active().filter(source=s).count() for s, _ in Hospital.SOURCE_CHOICES}
    return render(request, "hospitals/directory_import.html", {"form": form, "stats": stats})


