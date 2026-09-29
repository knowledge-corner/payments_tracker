import csv
import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.periods import add_months, month_start
from core.permissions import scoped_cases, selected_doctor, visible_doctors
from hospitals.models import Hospital
from payments.models import Payment

ZERO = Decimal("0")


def _parse_month(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m").date()
    except (TypeError, ValueError):
        return None


def date_filters(request):
    """Month range from ?from=YYYY-MM&to=YYYY-MM (default: last 12 months)."""
    today = timezone.localdate()
    end_month = _parse_month(request.GET.get("to")) or month_start(today)
    start_month = _parse_month(request.GET.get("from")) or add_months(end_month, -11)
    if start_month > end_month:
        start_month, end_month = end_month, start_month
    end_date = add_months(end_month, 1) - datetime.timedelta(days=1)
    return start_month, end_month, end_date


def base_context(request, start, end_month):
    return {
        "from_value": f"{start:%Y-%m}",
        "to_value": f"{end_month:%Y-%m}",
        "doctors": visible_doctors(request.user),
        "selected_doctor": selected_doctor(request),
    }


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


@login_required
def index(request):
    return render(request, "reports/index.html")


@login_required
def monthly(request):
    start, end_month, end = date_filters(request)
    cases = scoped_cases(request).filter(case_date__gte=start, case_date__lte=end)

    billed = {
        r["m"]: r for r in cases.annotate(m=TruncMonth("case_date")).values("m")
        .annotate(n=Count("id"), fees=Sum("fee")).order_by()
    }
    received = {
        r["m"]: r["total"] for r in Payment.objects.filter(
            case__in=scoped_cases(request), payment_date__gte=start, payment_date__lte=end,
        ).annotate(m=TruncMonth("payment_date")).values("m").annotate(total=Sum("amount")).order_by()
    }
    outstanding = {}
    for c in cases.with_totals().filter(outstanding__gt=0).only("case_date", "fee"):
        key = month_start(c.case_date)
        outstanding[key] = outstanding.get(key, ZERO) + c.outstanding

    rows, month = [], end_month
    while month >= start:
        b = billed.get(month, {})
        rows.append({
            "month": month,
            "cases": b.get("n", 0),
            "billed": b.get("fees") or ZERO,
            "received": received.get(month) or ZERO,
            "outstanding": outstanding.get(month, ZERO),
        })
        month = add_months(month, -1)
    totals = {k: sum(r[k] for r in rows) for k in ("cases", "billed", "received", "outstanding")}

    if request.GET.get("export") == "csv":
        return csv_response(
            "monthly_report.csv",
            ["Month", "Cases", "Billed", "Received (by payment date)", "Outstanding (cases of month)"],
            [[f"{r['month']:%b %Y}", r["cases"], r["billed"], r["received"], r["outstanding"]] for r in rows],
        )
    ctx = base_context(request, start, end_month)
    ctx.update({"rows": rows, "totals": totals})
    return render(request, "reports/monthly.html", ctx)


@login_required
def hospital_wise(request):
    start, end_month, end = date_filters(request)
    cases = (
        scoped_cases(request).filter(case_date__gte=start, case_date__lte=end)
        .with_totals().select_related("hospital")
    )
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

    if request.GET.get("export") == "csv":
        return csv_response(
            "hospital_report.csv",
            ["Hospital", "Cases", "Billed", "Received", "Outstanding", "Overdue"],
            [[r["hospital"].name, r["cases"], r["billed"], r["received"], r["outstanding"], r["overdue"]] for r in rows],
        )
    ctx = base_context(request, start, end_month)
    ctx.update({"rows": rows, "totals": totals, "sort": sort})
    return render(request, "reports/hospitals.html", ctx)


@login_required
def payment_history(request):
    start, end_month, end = date_filters(request)
    payments = (
        Payment.objects.filter(case__in=scoped_cases(request), payment_date__gte=start, payment_date__lte=end)
        .select_related("case__hospital", "case__doctor").order_by("-payment_date", "-id")
    )
    hospital = request.GET.get("hospital", "")
    mode = request.GET.get("mode", "")
    if hospital.isdigit():
        payments = payments.filter(case__hospital_id=hospital)
    if mode in dict(Payment.MODE_CHOICES):
        payments = payments.filter(mode=mode)
    summary = payments.aggregate(total=Sum("amount"), n=Count("id"))
    by_mode = payments.values("mode").annotate(total=Sum("amount")).order_by("-total")
    mode_labels = dict(Payment.MODE_CHOICES)

    if request.GET.get("export") == "csv":
        return csv_response(
            "payment_history.csv",
            ["Payment date", "Doctor", "Hospital", "Case date", "Case ref", "Amount", "Mode", "Reference", "Notes"],
            [[p.payment_date, p.case.doctor, p.case.hospital.name, p.case.case_date, p.case.patient_reference,
              p.amount, p.get_mode_display(), p.reference_no, p.notes] for p in payments],
        )
    ctx = base_context(request, start, end_month)
    ctx.update({
        "payments": payments[:300],
        "summary": summary,
        "by_mode": [{"label": mode_labels.get(r["mode"], r["mode"]), "total": r["total"]} for r in by_mode],
        "hospitals": Hospital.objects.order_by("name"),
        "hospital": hospital,
        "mode": mode,
        "modes": Payment.MODE_CHOICES,
    })
    return render(request, "reports/payments.html", ctx)
