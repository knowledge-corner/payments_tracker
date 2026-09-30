from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render

from cases.models import PaymentStatus
from core.periods import add_months, month_start
from core.permissions import scoped_cases, visible_doctors
from hospitals.models import Hospital
from payments.models import Payment

from .exports import export_response
from .filters import PERIODS, STATUS_CHOICES, apply_case_status, parse_filters

ZERO = Decimal("0")


def base_context(request, filters, **flags):
    ctx = {
        "f": filters,
        "periods": PERIODS,
        "status_choices": STATUS_CHOICES,
        "modes": Payment.MODE_CHOICES,
        "hospitals": Hospital.objects.order_by("name"),
        "doctors": visible_doctors(request.user),
        "selected_doctor": filters.doctor,
    }
    ctx.update(flags)
    return ctx


def export_format(request):
    fmt = request.GET.get("export")
    return fmt if fmt in ("csv", "xlsx") else None


def filtered_cases(request, filters):
    qs = scoped_cases(request).filter(**filters.date_filter("case_date"))
    if filters.hospital:
        qs = qs.filter(hospital=filters.hospital)
    if filters.q:
        qs = qs.filter(
            Q(patient_reference__icontains=filters.q) | Q(procedure_type__icontains=filters.q)
            | Q(notes__icontains=filters.q) | Q(hospital__name__icontains=filters.q)
        )
    return apply_case_status(qs.with_totals(), filters.status)


@login_required
def index(request):
    return render(request, "reports/index.html")


@login_required
def cases_report(request):
    """All cases matching the filters, with totals and Excel/CSV download."""
    filters = parse_filters(request, default_period="this_month")
    qs = filtered_cases(request, filters).select_related("hospital", "doctor").order_by("case_date", "id")
    summary = qs.aggregate(n=Count("id"), billed=Sum("fee"), received=Sum("total_paid"))
    summary["outstanding"] = qs.filter(outstanding__gt=0).aggregate(t=Sum("outstanding"))["t"] or ZERO

    fmt = export_format(request)
    if fmt:
        last_pay = Payment.objects.filter(case=OuterRef("pk")).order_by("-payment_date").values("payment_date")[:1]
        rows = [
            [c.case_date, str(c.doctor), c.hospital.name, c.procedure_type, c.patient_reference,
             c.fee, c.total_paid, c.outstanding, PaymentStatus.LABELS[c.status], c.due_date,
             c.days_overdue if c.status == PaymentStatus.OVERDUE else 0, c.last_payment, c.notes]
            for c in qs.annotate(last_payment=Subquery(last_pay))
        ]
        columns = [
            ("Case date", "date"), ("Doctor", "text"), ("Hospital", "text"), ("Procedure", "text"),
            ("Case / patient ref", "text"), ("Fee", "money"), ("Received", "money"), ("Outstanding", "money"),
            ("Status", "text"), ("Due date", "date"), ("Days overdue", "int"), ("Last payment", "date"), ("Notes", "text"),
        ]
        totals = ["TOTAL", f"{summary['n']} cases", "", "", "", summary["billed"] or ZERO,
                  summary["received"] or ZERO, summary["outstanding"], "", "", "", "", ""]
        return export_response(fmt, "cases_report", "Cases report", filters.describe(), columns, rows, totals)

    page = Paginator(qs.order_by("-case_date", "-id"), 50).get_page(request.GET.get("page"))
    ctx = base_context(request, filters, show_hospital=True, show_status=True, show_q=True)
    ctx.update({"page": page, "summary": summary})
    return render(request, "reports/cases.html", ctx)


@login_required
def monthly(request):
    filters = parse_filters(request, default_period="last_12")
    cases = scoped_cases(request).filter(**filters.date_filter("case_date"))
    payments = Payment.objects.filter(case__in=scoped_cases(request), **filters.date_filter("payment_date"))
    if filters.hospital:
        cases = cases.filter(hospital=filters.hospital)
        payments = payments.filter(case__hospital=filters.hospital)

    start = filters.start
    if start is None:
        first = cases.order_by("case_date").values_list("case_date", flat=True).first()
        start = first or month_start(filters.end)

    billed = {
        r["m"]: r for r in cases.annotate(m=TruncMonth("case_date")).values("m")
        .annotate(n=Count("id"), fees=Sum("fee")).order_by()
    }
    received = {
        r["m"]: r["total"] for r in payments.annotate(m=TruncMonth("payment_date"))
        .values("m").annotate(total=Sum("amount")).order_by()
    }
    outstanding = {}
    for c in cases.with_totals().filter(outstanding__gt=0).only("case_date", "fee"):
        key = month_start(c.case_date)
        outstanding[key] = outstanding.get(key, ZERO) + c.outstanding

    rows, month = [], month_start(filters.end)
    while month >= month_start(start):
        b = billed.get(month, {})
        rows.append({
            "month": month, "cases": b.get("n", 0), "billed": b.get("fees") or ZERO,
            "received": received.get(month) or ZERO, "outstanding": outstanding.get(month, ZERO),
        })
        month = add_months(month, -1)
    totals = {k: sum(r[k] for r in rows) for k in ("cases", "billed", "received", "outstanding")}

    fmt = export_format(request)
    if fmt:
        columns = [("Month", "text"), ("Cases", "int"), ("Billed", "money"),
                   ("Received (by payment date)", "money"), ("Outstanding (cases of month)", "money")]
        data = [[f"{r['month']:%b %Y}", r["cases"], r["billed"], r["received"], r["outstanding"]] for r in rows]
        total_row = ["TOTAL", totals["cases"], totals["billed"], totals["received"], totals["outstanding"]]
        return export_response(fmt, "monthly_summary", "Monthly summary", filters.describe(), columns, data, total_row)

    ctx = base_context(request, filters, show_hospital=True)
    ctx.update({"rows": rows, "totals": totals})
    return render(request, "reports/monthly.html", ctx)


@login_required
def hospital_wise(request):
    filters = parse_filters(request, default_period="this_fy")
    cases = filtered_cases(request, filters).select_related("hospital")
    data = {}
    for c in cases:
        row = data.setdefault(c.hospital_id, {
            "hospital": c.hospital, "cases": 0, "billed": ZERO, "received": ZERO,
            "outstanding": ZERO, "overdue": ZERO,
        })
        row["cases"] += 1
        row["billed"] += c.fee
        row["received"] += c.total_paid
        row["outstanding"] += max(c.outstanding, ZERO)
        if c.status == "overdue":
            row["overdue"] += c.outstanding
    sort = request.GET.get("sort", "outstanding")
    if sort not in ("outstanding", "billed", "cases"):
        sort = "outstanding"
    rows = sorted(data.values(), key=lambda r: r[sort], reverse=True)
    totals = {k: sum(r[k] for r in rows) for k in ("cases", "billed", "received", "outstanding", "overdue")}

    fmt = export_format(request)
    if fmt:
        columns = [("Hospital", "text"), ("Cases", "int"), ("Billed", "money"), ("Received", "money"),
                   ("Outstanding", "money"), ("Overdue", "money")]
        data_rows = [[r["hospital"].name, r["cases"], r["billed"], r["received"], r["outstanding"], r["overdue"]]
                     for r in rows]
        total_row = ["TOTAL", totals["cases"], totals["billed"], totals["received"], totals["outstanding"], totals["overdue"]]
        return export_response(fmt, "hospital_wise", "Hospital-wise billing", filters.describe(), columns, data_rows, total_row)

    ctx = base_context(request, filters, show_status=True, show_q=True)
    ctx.update({"rows": rows, "totals": totals, "sort": sort})
    return render(request, "reports/hospitals.html", ctx)


@login_required
def payment_history(request):
    filters = parse_filters(request, default_period="this_month")
    payments = (
        Payment.objects.filter(case__in=scoped_cases(request), **filters.date_filter("payment_date"))
        .select_related("case__hospital", "case__doctor").order_by("-payment_date", "-id")
    )
    if filters.hospital:
        payments = payments.filter(case__hospital=filters.hospital)
    if filters.mode:
        payments = payments.filter(mode=filters.mode)
    if filters.q:
        payments = payments.filter(
            Q(reference_no__icontains=filters.q) | Q(notes__icontains=filters.q)
            | Q(case__patient_reference__icontains=filters.q)
        )
    summary = payments.aggregate(total=Sum("amount"), n=Count("id"))
    mode_labels = dict(Payment.MODE_CHOICES)
    by_mode = [
        {"label": mode_labels.get(r["mode"], r["mode"]), "total": r["total"]}
        for r in payments.values("mode").annotate(total=Sum("amount")).order_by("-total")
    ]

    fmt = export_format(request)
    if fmt:
        columns = [("Payment date", "date"), ("Doctor", "text"), ("Hospital", "text"), ("Case date", "date"),
                   ("Case / patient ref", "text"), ("Amount", "money"), ("Mode", "text"), ("Reference", "text"),
                   ("Notes", "text")]
        rows = [[p.payment_date, str(p.case.doctor), p.case.hospital.name, p.case.case_date, p.case.patient_reference,
                 p.amount, p.get_mode_display(), p.reference_no, p.notes] for p in payments]
        total_row = ["TOTAL", f"{summary['n']} payments", "", "", "", summary["total"] or ZERO, "", "", ""]
        return export_response(fmt, "payment_history", "Payment history", filters.describe(), columns, rows, total_row)

    page = Paginator(payments, 50).get_page(request.GET.get("page"))
    ctx = base_context(request, filters, show_hospital=True, show_mode=True, show_q=True)
    ctx.update({"page": page, "summary": summary, "by_mode": by_mode})
    return render(request, "reports/payments.html", ctx)
