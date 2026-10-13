"""Builds the scheduled notifications. Safe to run as often as you like (hourly is ideal):
each notification is sent once, at or after the user's chosen hour."""
import datetime

from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone

from cases.models import Case
from core.templatetags.money import inr
from payments.models import Payment
from payments.services import receivables_for

from .models import NotificationKind, NotificationPreference, NotifiedCase, PushSubscription
from .push import notify


def _names(cases, limit=2):
    parts = [f"{c.hospital.name} {inr(c.outstanding)}" for c in cases[:limit]]
    more = len(cases) - limit
    return ", ".join(parts) + (f" +{more} more" if more > 0 else "")


def _notify_cases(user, kind, cases, key_fn, title, url, subscriptions=None):
    """Bundle not-yet-notified case events into one notification, then remember them."""
    marked = set(NotifiedCase.objects.filter(user=user, key__in=[key_fn(c) for c in cases]).values_list("key", flat=True))
    new = [c for c in cases if key_fn(c) not in marked]
    if not new:
        return 0
    total = sum(c.outstanding for c in new)
    body = f"{len(new)} case{'s' if len(new) != 1 else ''} ({inr(total)}): {_names(new)}"
    sent = notify(user, kind, title(len(new)), body, url=url, subscriptions=subscriptions)
    if sent:
        NotifiedCase.objects.bulk_create([NotifiedCase(user=user, key=key_fn(c)) for c in new], ignore_conflicts=True)
    return sent


def run_for_user(user, now=None):
    """Send due notifications to the user's phones.

    Each phone chooses its reminders (PushSubscription.doctor): all cases of the
    practice, or one anaesthetist's cases (default: the user's own). Devices with the same choice are handled
    together, and every notification is sent once per choice.
    """
    now = timezone.localtime(now or timezone.now())
    today = now.date()
    prefs = NotificationPreference.for_user(user)
    if not prefs.push_enabled or now.hour < prefs.summary_hour:
        return {}
    groups = {}
    for sub in PushSubscription.objects.filter(user=user).select_related("doctor"):
        groups.setdefault(sub.doctor_id, []).append(sub)
    if not groups:
        return {}
    all_cases = receivables_for(user, today)
    results = {}
    for doctor_id, subs in groups.items():
        doctor = subs[0].doctor
        cases = all_cases if doctor_id is None else [c for c in all_cases if c.doctor_id == doctor_id]
        tag = "" if doctor_id is None else f"d{doctor_id}:"
        who = f" ({doctor})" if doctor else ""
        for name, count in _run_group(user, prefs, today, cases, subs, tag, who, doctor_id).items():
            results[name] = results.get(name, 0) + count
    return results


def _run_group(user, prefs, today, cases, subs, tag, who, doctor_id):
    results = {}
    overdue = [c for c in cases if c.status == "overdue"]
    followups = [c for c in cases if c.reminder.due]

    # One reminder per case per reminder date (expected payment date, or a date set in a follow-up).
    if prefs.wants(NotificationKind.FOLLOWUP) and followups:
        results["followup"] = _notify_cases(
            user, NotificationKind.FOLLOWUP, followups, lambda c: f"{tag}followup:{c.pk}:{c.reminder.last_trigger}",
            lambda n: f"Payment reminder{who}: {n} case{'s' if n != 1 else ''} to follow up",
            reverse("receivables:list") + "?view=followup" + (f"&doctor={doctor_id}" if doctor_id else ""),
            subscriptions=subs,
        )
    if prefs.wants(NotificationKind.DAILY_SUMMARY) and (followups or overdue):
        outstanding = sum(c.outstanding for c in cases)
        parts = []
        if followups:
            parts.append(f"{len(followups)} reminder{'s' if len(followups) != 1 else ''} due")
        if overdue:
            parts.append(f"{len(overdue)} overdue ({inr(sum(c.outstanding for c in overdue))})")
        parts.append(f"{inr(outstanding)} outstanding")
        results["daily"] = notify(
            user, NotificationKind.DAILY_SUMMARY, f"Good morning - today's payments{who}", " · ".join(parts),
            url=reverse("dashboard:home"), key=f"{tag}daily:{today}", subscriptions=subs,
        )
    if prefs.wants(NotificationKind.WEEKLY) and today.weekday() == 0:
        start = today - datetime.timedelta(days=7)
        end = today - datetime.timedelta(days=1)
        scope = Case.objects.for_user(user)
        if doctor_id:
            scope = scope.filter(doctor_id=doctor_id)
        billed = scope.filter(case_date__range=(start, end)).aggregate(n=Count("id"), t=Sum("fee"))
        received = Payment.objects.filter(case__in=scope, payment_date__range=(start, end)).aggregate(t=Sum("amount"))["t"]
        outstanding = sum(c.outstanding for c in cases)
        body = (f"{billed['n']} case{'s' if billed['n'] != 1 else ''} · {inr(billed['t'])} billed · "
                f"{inr(received)} received · {inr(outstanding)} outstanding")
        year, week, _ = today.isocalendar()
        results["weekly"] = notify(
            user, NotificationKind.WEEKLY, f"Last week ({start:%d %b} - {end:%d %b}){who}", body,
            url=reverse("reports:monthly"), key=f"{tag}weekly:{year}-{week}", subscriptions=subs,
        )
    return results


def record_run(now=None):
    from core.models import AppSettings

    AppSettings.objects.filter(pk=AppSettings.load().pk).update(notifications_last_run=now or timezone.now())


def sender_status(now=None):
    """(last_run, healthy) - healthy if the automatic sender ran within the last 26 hours."""
    from core.models import AppSettings

    last = AppSettings.load().notifications_last_run
    now = now or timezone.now()
    return last, bool(last and now - last <= datetime.timedelta(hours=26))


def upcoming_reminders(user, limit=3, doctor=None):
    """Next reminder dates for the user's unpaid cases (for the settings page)."""
    cases = receivables_for(user)
    if doctor is not None:
        cases = [c for c in cases if c.doctor_id == doctor.pk]
    rows = sorted(((c.reminder.next_trigger, c) for c in cases if c.reminder.next_trigger), key=lambda r: r[0])
    return [{"date": d, "case": c} for d, c in rows[:limit]], sum(1 for c in cases if c.reminder.due)


def run_scheduled(now=None):
    """Run for every active user who has at least one device subscribed."""
    user_ids = PushSubscription.objects.filter(user__is_active=True).values_list("user_id", flat=True).distinct()
    from accounts.models import User

    summary = {"users": 0, "sent": 0}
    for user in User.objects.filter(pk__in=list(user_ids)):
        summary["users"] += 1
        summary["sent"] += sum(run_for_user(user, now).values())
    record_run(now)
    return summary
