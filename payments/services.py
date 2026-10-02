"""
Receivables and follow-up business rules.

Kept free of request/response code so the same logic can back a future
REST API or native app.
"""
import datetime
from dataclasses import dataclass

from django.utils import timezone

from cases.models import Case
from core.models import AppSettings


@dataclass
class ReminderState:
    due: bool
    last_trigger: datetime.date | None  # most recent reminder date already reached
    next_trigger: datetime.date | None  # next upcoming reminder date
    snoozed_until: datetime.date | None


def reminder_offsets(settings, up_to_age):
    """Reminder ages (in days) up to `up_to_age`, plus the next one after it."""
    base = settings.reminder_days_list
    offsets = list(base)
    repeat = settings.repeat_reminder_every_days
    if repeat and base:
        nxt = base[-1] + repeat
        while nxt <= up_to_age + repeat:
            offsets.append(nxt)
            nxt += repeat
    return offsets


def reminder_state(case, settings=None, today=None):
    """Work out whether a case needs a payment follow-up today.

    A reminder fires when an unpaid case reaches one of the configured ages
    (e.g. 7/14/21 days after the case date). It is cleared by recording a
    follow-up on/after that reminder date, and hidden while snoozed.
    """
    settings = settings or AppSettings.load()
    today = today or timezone.localdate()
    age = (today - case.case_date).days
    offsets = reminder_offsets(settings, age)

    reached = [o for o in offsets if o <= age]
    upcoming = [o for o in offsets if o > age]
    last_trigger = case.case_date + datetime.timedelta(days=reached[-1]) if reached else None
    next_trigger = case.case_date + datetime.timedelta(days=upcoming[0]) if upcoming else None

    snoozed = case.followup_snoozed_until if (
        case.followup_snoozed_until and case.followup_snoozed_until > today
    ) else None

    last_followup = getattr(case, "last_followup_date", None)
    if last_followup is None and not hasattr(case, "last_followup_date"):
        latest = case.followups.order_by("-followup_date").first()
        last_followup = latest.followup_date if latest else None

    due = (
        case.balance > 0
        and last_trigger is not None
        and snoozed is None
        and (last_followup is None or last_followup < last_trigger)
    )
    return ReminderState(due=due, last_trigger=last_trigger, next_trigger=next_trigger, snoozed_until=snoozed)


def receivables_for(user, today=None):
    """Outstanding cases visible to `user`, annotated with totals, age and reminder state."""
    settings = AppSettings.load()
    today = today or timezone.localdate()
    cases = list(
        Case.objects.for_user(user)
        .with_totals(today)
        .with_last_followup()
        .filter(outstanding__gt=0)
        .select_related("hospital", "doctor", "surgeon")
        .order_by("case_date", "id")
    )
    for case in cases:
        case.reminder = reminder_state(case, settings, today)
    return cases


def snooze(case, days):
    case.followup_snoozed_until = timezone.localdate() + datetime.timedelta(days=days)
    case.save(update_fields=["followup_snoozed_until", "updated_at"])


def apply_followup(followup):
    """After a follow-up is logged, pause reminders until any promised payment date."""
    case = followup.case
    if followup.promised_payment_date and followup.promised_payment_date > timezone.localdate():
        case.followup_snoozed_until = followup.promised_payment_date
    else:
        case.followup_snoozed_until = None
    case.save(update_fields=["followup_snoozed_until", "updated_at"])
