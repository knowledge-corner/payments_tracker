from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from contacts.services import attach_call_targets
from core.periods import PERIODS, period_range
from core.permissions import scoped_cases, selected_doctor, visible_doctors
from payments.models import Payment
from payments.services import receivables_for

ZERO = Decimal("0")


@login_required
def home(request):
    today = timezone.localdate()
    period = request.GET.get("period", "month")
    if period not in dict(PERIODS):
        period = "month"
    start, end = period_range(period, today)

    cases = scoped_cases(request)
    payments = Payment.objects.filter(case__in=cases)
    if start:
        period_cases = cases.filter(case_date__gte=start, case_date__lte=end)
        period_payments = payments.filter(payment_date__gte=start, payment_date__lte=end)
    else:
        period_cases, period_payments = cases, payments

    earnings = period_cases.aggregate(total=Sum("fee"), n=Count("id"))
    received = period_payments.aggregate(total=Sum("amount"))["total"] or ZERO
    month_cases = cases.filter(case_date__year=today.year, case_date__month=today.month).count()

    open_cases = receivables_for(request.user, today)
    doctor = selected_doctor(request)
    if request.user.is_app_admin and doctor:
        open_cases = [c for c in open_cases if c.doctor_id == doctor.pk]

    overdue = [c for c in open_cases if c.status == "overdue"]
    pending = [c for c in open_cases if c.status != "overdue"]
    followups = [c for c in open_cases if c.reminder.due]

    # Action required: follow-ups due and overdue cases first, then oldest pending.
    def priority(c):
        return (0 if c.reminder.due else 1, 0 if c.status == "overdue" else 1, c.case_date)

    action_required = attach_call_targets(sorted({c.pk: c for c in followups + overdue}.values(), key=priority)[:6])

    context = {
        "period": period,
        "periods": PERIODS,
        "total_earnings": earnings["total"] or ZERO,
        "period_case_count": earnings["n"],
        "amount_received": received,
        "outstanding": sum((c.outstanding for c in open_cases), ZERO),
        "overdue_amount": sum((c.outstanding for c in overdue), ZERO),
        "cases_this_month": month_cases,
        "pending_count": len(pending),
        "pending_amount": sum((c.outstanding for c in pending), ZERO),
        "overdue_count": len(overdue),
        "followup_count": len(followups),
        "action_required": action_required,
        "action_total": len({c.pk for c in followups + overdue}),
        "recent_payments": payments.select_related("case__hospital").order_by("-payment_date", "-id")[:3],
        "doctors": visible_doctors(request.user),
        "selected_doctor": doctor,
    }
    return render(request, "dashboard/home.html", context)
