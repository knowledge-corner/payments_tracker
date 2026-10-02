from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Doctor
from cases.models import Case
from core.permissions import require_doctor_profile

from .forms import AffiliationForm, ContactForm, SurgeonForm, SurgeonHospitalForm
from .models import Contact, ContactAffiliation, Surgeon, SurgeonHospital
from .services import contacts_for_hospital


def _scope(user):
    qs = Contact.objects.select_related("doctor")
    return qs if user.is_app_admin else qs.filter(doctor__user=user)


def _get(request, pk):
    contact = get_object_or_404(Contact.objects.select_related("doctor"), pk=pk)
    if not request.user.is_app_admin and contact.doctor.user_id != request.user.id:
        raise PermissionDenied
    return contact


@login_required
def contact_list(request):
    q = request.GET.get("q", "").strip()
    contacts = _scope(request.user)
    if q:
        contacts = contacts.filter(
            Q(name__icontains=q) | Q(phone__icontains=q)
            | Q(affiliations__hospital__name__icontains=q, affiliations__end_date__isnull=True)
        ).distinct()
    contacts = list(contacts.prefetch_related("affiliations__hospital"))
    for c in contacts:
        c.current = [a for a in c.affiliations.all() if a.is_current]
    return render(request, "contacts/contact_list.html", {"contacts": contacts, "q": q})


@require_doctor_profile
def contact_add(request):
    form = ContactForm(request.POST or None)
    link_form = AffiliationForm(request.POST or None, prefix="link", initial={"hospital": request.GET.get("hospital")})
    link_form.fields["hospital"].required = False
    if request.method == "POST" and form.is_valid() and link_form.is_valid():
        contact = form.save(commit=False)
        contact.doctor = request.user.doctor_profile or Doctor.objects.filter(pk=request.POST.get("doctor") or 0).first()
        if contact.doctor is None:
            messages.error(request, "Choose the doctor this contact belongs to.")
            return redirect(request.get_full_path())
        contact.save()
        if link_form.cleaned_data.get("hospital"):
            link = link_form.save(commit=False)
            link.contact = contact
            link.save()
        messages.success(request, f"{contact} saved.")
        return redirect(request.GET.get("next") or contact.get_absolute_url())
    return render(request, "contacts/contact_form.html", {
        "form": form, "link_form": link_form, "contact": None,
        "doctors": Doctor.objects.filter(is_active=True) if request.user.is_app_admin and not request.user.doctor_profile else None,
    })


@login_required
def contact_edit(request, pk):
    contact = _get(request, pk)
    form = ContactForm(request.POST or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contact updated.")
        return redirect(contact)
    return render(request, "contacts/contact_form.html", {"form": form, "contact": contact, "link_form": None})


@login_required
def contact_detail(request, pk):
    contact = _get(request, pk)
    links = contact.affiliations.select_related("hospital").order_by("end_date", "-start_date")
    form = AffiliationForm(prefix="link", initial={"start_date": timezone.localdate()})
    recent_cases = (Case.objects.filter(contact=contact).with_totals()
                    .select_related("hospital").order_by("-case_date")[:10])
    return render(request, "contacts/contact_detail.html", {
        "contact": contact,
        "current_links": [link for link in links if link.is_current],
        "past_links": [link for link in links if not link.is_current],
        "form": form, "recent_cases": recent_cases,
    })


@login_required
@require_POST
def link_add(request, pk):
    contact = _get(request, pk)
    form = AffiliationForm(request.POST, prefix="link")
    if form.is_valid():
        start = form.cleaned_data["start_date"]
        if form.cleaned_data["moved_from_others"]:
            contact.affiliations.filter(end_date__isnull=True).exclude(
                hospital=form.cleaned_data["hospital"]).update(end_date=start)
        link = form.save(commit=False)
        link.contact = contact
        if link.is_primary:
            ContactAffiliation.objects.current().filter(
                contact__doctor=contact.doctor, hospital=link.hospital,
            ).update(is_primary=False)
        link.save()
        messages.success(request, f"{contact} now linked to {link.hospital}.")
    else:
        messages.error(request, "Please choose a hospital.")
    return redirect(contact)


@login_required
@require_POST
def link_end(request, pk, link_pk):
    contact = _get(request, pk)
    link = get_object_or_404(ContactAffiliation, pk=link_pk, contact=contact)
    link.end_date = timezone.localdate()
    link.is_primary = False
    link.save(update_fields=["end_date", "is_primary", "updated_at"])
    messages.info(request, f"{contact} no longer listed at {link.hospital}. Past cases keep the history.")
    return redirect(contact)


@login_required
@require_POST
def link_primary(request, pk, link_pk):
    contact = _get(request, pk)
    link = get_object_or_404(ContactAffiliation, pk=link_pk, contact=contact, end_date__isnull=True)
    ContactAffiliation.objects.current().filter(
        contact__doctor=contact.doctor, hospital=link.hospital,
    ).update(is_primary=False)
    link.is_primary = True
    link.save(update_fields=["is_primary", "updated_at"])
    messages.success(request, f"{contact} is now the main contact at {link.hospital}.")
    return redirect(contact)


@login_required
def for_hospital(request):
    """JSON for the Add Case form: contacts and surgeons ordered for this hospital."""
    doctor = request.user.doctor_profile
    if request.user.is_app_admin and request.GET.get("doctor", "").isdigit():
        doctor = Doctor.objects.filter(pk=request.GET["doctor"]).first()
    hospital_id = request.GET.get("hospital", "")
    empty = {"here": [], "others": [], "suggested_contact": None,
             "surgeons_here": [], "surgeons_others": [], "suggested_surgeon": None}
    if doctor is None or not hospital_id.isdigit():
        return JsonResponse(empty)
    last = (Case.objects.filter(doctor=doctor, hospital_id=hospital_id)
            .order_by("-case_date", "-id").values("contact_id", "surgeon_id").first()) or {}
    here, others = contacts_for_hospital(doctor, int(hospital_id))

    def item(contact):
        return {"id": contact.pk, "label": f"{contact.name} - {contact.get_role_display()}", "phone": contact.best_phone}

    here_ids = {c.pk for c, _ in here}
    suggested = last.get("contact_id") if last.get("contact_id") in here_ids else (here[0][0].pk if here else None)

    surgeons = list(Surgeon.objects.filter(doctor=doctor, is_active=True).prefetch_related("hospital_links"))
    s_here = [s for s in surgeons if any(link.hospital_id == int(hospital_id) for link in s.hospital_links.all())]
    s_others = [s for s in surgeons if s not in s_here]
    return JsonResponse({
        "here": [item(c) for c, _link in here],
        "others": [item(c) for c in others],
        "suggested_contact": suggested,
        "surgeons_here": [{"id": s.pk, "label": s.name} for s in s_here],
        "surgeons_others": [{"id": s.pk, "label": s.name} for s in s_others],
        "suggested_surgeon": last.get("surgeon_id") if last.get("surgeon_id") in {s.pk for s in s_here} else None,
    })


# --------------------------------------------------------------------------- #
# Surgeons (private to each anaesthetist; linked to hospitals via SurgeonHospital)
# --------------------------------------------------------------------------- #

def _get_surgeon(request, pk):
    surgeon = get_object_or_404(Surgeon.objects.select_related("doctor"), pk=pk)
    if not request.user.is_app_admin and surgeon.doctor.user_id != request.user.id:
        raise PermissionDenied
    return surgeon


@login_required
def surgeon_list(request):
    q = request.GET.get("q", "").strip()
    surgeons = Surgeon.objects.select_related("doctor")
    if not request.user.is_app_admin:
        surgeons = surgeons.filter(doctor__user=request.user)
    if q:
        surgeons = surgeons.filter(Q(name__icontains=q) | Q(phone__icontains=q)
                                   | Q(hospital_links__hospital__name__icontains=q)).distinct()
    surgeons = surgeons.prefetch_related("hospital_links__hospital").annotate(case_count=Count("cases"))
    return render(request, "contacts/surgeon_list.html", {"surgeons": surgeons, "q": q})


@require_doctor_profile
def surgeon_add(request):
    form = SurgeonForm(request.POST or None)
    link_form = SurgeonHospitalForm(request.POST or None, prefix="link")
    link_form.fields["hospital"].required = False
    if request.method == "POST" and form.is_valid() and link_form.is_valid():
        surgeon = form.save(commit=False)
        surgeon.doctor = request.user.doctor_profile or Doctor.objects.filter(pk=request.POST.get("doctor") or 0).first()
        if surgeon.doctor is None:
            messages.error(request, "Choose the doctor this surgeon belongs to.")
            return redirect(request.get_full_path())
        surgeon.save()
        surgeon.link_hospital(link_form.cleaned_data.get("hospital"))
        messages.success(request, f"{surgeon} saved.")
        return redirect(surgeon)
    return render(request, "contacts/surgeon_form.html", {
        "form": form, "link_form": link_form, "surgeon": None,
        "doctors": Doctor.objects.filter(is_active=True) if request.user.is_app_admin and not request.user.doctor_profile else None,
    })


@login_required
def surgeon_edit(request, pk):
    surgeon = _get_surgeon(request, pk)
    form = SurgeonForm(request.POST or None, instance=surgeon)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Surgeon updated.")
        return redirect(surgeon)
    return render(request, "contacts/surgeon_form.html", {"form": form, "surgeon": surgeon, "link_form": None})


@login_required
def surgeon_detail(request, pk):
    surgeon = _get_surgeon(request, pk)
    cases = Case.objects.filter(surgeon=surgeon).with_totals()
    per_hospital = {
        r["hospital_id"]: r for r in cases.values("hospital_id").annotate(n=Count("id"), billed=Sum("fee")).order_by()
    }
    links = list(surgeon.hospital_links.select_related("hospital"))
    for link in links:
        stats = per_hospital.get(link.hospital_id, {})
        link.case_count, link.billed = stats.get("n", 0), stats.get("billed") or 0
    return render(request, "contacts/surgeon_detail.html", {
        "surgeon": surgeon, "links": links, "form": SurgeonHospitalForm(prefix="link"),
        "recent_cases": cases.select_related("hospital").order_by("-case_date")[:10],
    })


@login_required
@require_POST
def surgeon_link_add(request, pk):
    surgeon = _get_surgeon(request, pk)
    form = SurgeonHospitalForm(request.POST, prefix="link")
    if form.is_valid():
        surgeon.link_hospital(form.cleaned_data["hospital"])
        messages.success(request, f"{surgeon} linked to {form.cleaned_data['hospital']}.")
    else:
        messages.error(request, "Please choose a hospital.")
    return redirect(surgeon)


@login_required
@require_POST
def surgeon_link_remove(request, pk, link_pk):
    surgeon = _get_surgeon(request, pk)
    SurgeonHospital.objects.filter(pk=link_pk, surgeon=surgeon).delete()
    messages.info(request, "Hospital removed from this surgeon. Past cases are unchanged.")
    return redirect(surgeon)
