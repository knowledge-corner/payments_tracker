from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.permissions import require_doctor_profile, scoped_cases, selected_doctor, visible_doctors
from hospitals.models import Hospital
from payments.models import Payment
from payments.services import reminder_state

from .forms import COMMON_PROCEDURES, CaseForm
from .models import Case, PaymentStatus


def procedure_suggestions(user):
    recent = (
        Case.objects.for_user(user).exclude(procedure_type="")
        .order_by("-case_date").values_list("procedure_type", flat=True)[:200]
    )
    seen, result = set(), []
    for name in list(recent) + COMMON_PROCEDURES:
        if name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result[:25]


def get_case_for_user(request, pk):
    case = get_object_or_404(Case.objects.select_related("hospital", "doctor"), pk=pk)
    if not request.user.is_app_admin and case.doctor.user_id != request.user.id:
        raise PermissionDenied
    return case


@login_required
def case_list(request):
    qs = scoped_cases(request).with_totals().select_related("hospital", "doctor")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    hospital = request.GET.get("hospital", "")
    month = request.GET.get("month", "")  # YYYY-MM
    if q:
        qs = qs.filter(
            Q(patient_reference__icontains=q) | Q(procedure_type__icontains=q)
            | Q(hospital__name__icontains=q) | Q(notes__icontains=q)
        )
    if status in PaymentStatus.LABELS:
        qs = qs.filter(status=status)
    elif status == "unpaid":
        qs = qs.filter(outstanding__gt=0)
    if hospital.isdigit():
        qs = qs.filter(hospital_id=hospital)
    if len(month) == 7 and month[4] == "-":
        try:
            qs = qs.filter(case_date__year=int(month[:4]), case_date__month=int(month[5:]))
        except ValueError:
            pass
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "q": q,
        "status": status,
        "hospital": hospital,
        "month": month,
        "status_choices": PaymentStatus.CHOICES,
        "hospitals": Hospital.objects.order_by("name"),
        "doctors": visible_doctors(request.user),
        "selected_doctor": selected_doctor(request),
    }
    return render(request, "cases/case_list.html", context)


@require_doctor_profile
def case_add(request):
    user = request.user
    initial = {}
    last_case = Case.objects.for_user(user).order_by("-created_at").first()
    hospital_id = request.GET.get("hospital")
    if hospital_id and hospital_id.isdigit():
        initial["hospital"] = hospital_id
    elif last_case:
        initial["hospital"] = last_case.hospital_id
    if request.GET.get("date"):
        initial["case_date"] = request.GET["date"]
    if initial.get("hospital"):
        h = Hospital.objects.filter(pk=initial["hospital"]).first()
        if h:
            initial["fee"] = int(h.default_fee) if h.default_fee == int(h.default_fee) else h.default_fee
    if user.is_app_admin and last_case:
        initial["doctor"] = last_case.doctor_id

    form = CaseForm(request.POST or None, user=user, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            case = form.save(commit=False)
            if not user.is_app_admin:
                case.doctor = user.doctor_profile
            case.created_by = user
            case.save()
            if form.cleaned_data.get("paid_now"):
                Payment.objects.create(
                    case=case,
                    amount=form.cleaned_data["paid_amount"],
                    payment_date=case.case_date,
                    mode=form.cleaned_data.get("paid_mode") or "upi",
                    created_by=user,
                )
        messages.success(request, f"Case saved: {case.hospital} - {case.fee:.0f}")
        if "save_add" in request.POST:
            return redirect(f"{reverse('cases:add')}?hospital={case.hospital_id}&date={case.case_date:%Y-%m-%d}")
        return redirect("dashboard:home")
    return render(request, "cases/case_form.html", {
        "form": form, "procedures": procedure_suggestions(user), "is_new": True,
    })


@login_required
def case_edit(request, pk):
    case = get_case_for_user(request, pk)
    form = CaseForm(request.POST or None, instance=case, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Case updated.")
        return redirect(case)
    return render(request, "cases/case_form.html", {
        "form": form, "case": case, "procedures": procedure_suggestions(request.user), "is_new": False,
    })


@login_required
def case_detail(request, pk):
    get_case_for_user(request, pk)
    case = (
        Case.objects.with_totals().with_last_followup()
        .select_related("hospital", "doctor").get(pk=pk)
    )
    context = {
        "case": case,
        "payments": case.payments.all(),
        "followups": case.followups.all(),
        "reminder": reminder_state(case) if case.outstanding > 0 else None,
    }
    return render(request, "cases/case_detail.html", context)


@login_required
def case_delete(request, pk):
    case = get_case_for_user(request, pk)
    if request.method == "POST":
        case.delete()
        messages.success(request, "Case deleted.")
        return redirect("cases:list")
    return render(request, "cases/case_confirm_delete.html", {"case": case})
