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
    """Tell phones that follow this case's anaesthetist (or the whole practice) that a payment was recorded
    (except the phone that recorded it)."""
    if not created:
        return
    case = instance.case
    source_device = getattr(instance, "_device_key", "")

    def send():
        subs = PushSubscription.objects.filter(Q(doctor_id=case.doctor_id) | Q(doctor__isnull=True)).select_related("user")
        if source_device:
            subs = subs.exclude(device_key=source_device)
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
