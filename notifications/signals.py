from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.templatetags.money import inr
from payments.models import Payment

from .models import NotificationKind
from .push import notify


@receiver(post_save, sender=Payment)
def payment_recorded(sender, instance, created, **kwargs):
    """Tell the doctor when somebody else (admin, import) records a payment on their case."""
    if not created:
        return
    case = instance.case
    doctor_user = case.doctor.user
    if instance.created_by_id == doctor_user.pk:
        return

    def send():
        notify(
            doctor_user, NotificationKind.PAYMENT, "Payment recorded",
            f"{inr(instance.amount)} from {case.hospital.name} for the case of {case.case_date:%d %b %Y}",
            url=case.get_absolute_url(), key=f"payment:{instance.pk}",
        )

    transaction.on_commit(send)
