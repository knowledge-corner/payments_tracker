from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.templatetags.money import inr
from payments.models import Payment

from .models import NotificationKind, PushSubscription
from .push import notify


@receiver(post_save, sender=Payment)
def payment_recorded(sender, instance, created, **kwargs):
    """Tell users whose reminders cover this case's anaesthetist (or the whole practice) that a payment was recorded
    (except the person who recorded it)."""
    if not created:
        return
    case = instance.case

    def send():
        subs = PushSubscription.objects.filter(Q(doctor_id=case.doctor_id) | Q(doctor__isnull=True)).select_related("user")
        if instance.created_by_id:
            subs = subs.exclude(user_id=instance.created_by_id)  # not the person who recorded it
        by_user = {}
        for sub in subs:
            by_user.setdefault(sub.user, []).append(sub)
        for user, group in by_user.items():
            notify(
                user, NotificationKind.PAYMENT, f"Payment recorded ({case.doctor})",
                f"{inr(instance.amount)} from {case.hospital.name} for the case of {case.case_date:%d %b %Y}",
                url=case.get_absolute_url(), key=f"payment:{instance.pk}", subscriptions=group,
            )

    transaction.on_commit(send)
