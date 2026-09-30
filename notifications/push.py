"""Sending push notifications to a user's devices, honouring their preferences."""
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import webpush
from .models import NotificationPreference, PushSubscription, SentNotification

logger = logging.getLogger(__name__)


def vapid_keys():
    """(private, public, subject). From env vars, else generated once and stored in DATA_DIR."""
    private = getattr(settings, "VAPID_PRIVATE_KEY", "")
    public = getattr(settings, "VAPID_PUBLIC_KEY", "")
    subject = getattr(settings, "VAPID_SUBJECT", "") or "mailto:admin@payments-tracker.app"
    if private and public:
        return private, public, subject
    path = settings.DATA_DIR / "vapid_keys.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        private, public = webpush.generate_vapid_keys()
        data = {"private": private, "public": public}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return data["private"], data["public"], subject


def public_key():
    return vapid_keys()[1]


def notify(user, kind, title, body, url="/", key=None):
    """Send to all of the user's devices if their preferences allow it.

    `key` makes the notification one-off (e.g. one morning summary per day).
    Returns the number of devices reached.
    """
    prefs = NotificationPreference.for_user(user)
    if not prefs.wants(kind):
        return 0
    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        return 0
    if key and SentNotification.objects.filter(user=user, key=key).exists():
        return 0

    private, public, subject = vapid_keys()
    payload = {"title": title, "body": body, "url": url, "tag": kind}
    delivered = 0
    for sub in subscriptions:
        try:
            webpush.send(sub.endpoint, sub.p256dh, sub.auth, payload,
                         private_b64=private, public_b64=public, subject=subject)
            sub.last_success_at = timezone.now()
            sub.failure_count = 0
            sub.save(update_fields=["last_success_at", "failure_count"])
            delivered += 1
        except webpush.PushGone:
            sub.delete()  # browser unsubscribed or app uninstalled
        except Exception as exc:  # network error, push service down, ...
            logger.warning("Push to %s failed: %s", user, exc)
            sub.failure_count += 1
            if sub.failure_count >= 10:
                sub.delete()
            else:
                sub.save(update_fields=["failure_count"])
    if delivered:
        try:
            with transaction.atomic():
                SentNotification.objects.create(
                    user=user, kind=kind, key=key or f"{kind}:{timezone.now().isoformat()}",
                    title=title[:120], body=body[:300], url=url[:200], devices=delivered,
                )
        except IntegrityError:
            pass
    return delivered
