import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import NotificationPreferenceForm
from .models import NotificationKind, NotificationPreference, PushSubscription, SentNotification
from accounts.models import Doctor

from .push import notify, public_key
from .services import run_scheduled, sender_status, upcoming_reminders


@login_required
def settings_page(request):
    prefs = NotificationPreference.for_user(request.user)
    form = NotificationPreferenceForm(request.POST or None, instance=prefs)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Notification settings saved.")
        return redirect("notifications:settings")
    devices = list(PushSubscription.objects.filter(user=request.user).select_related("doctor"))
    this_scope = devices[0].doctor if devices else request.user.doctor_profile
    return render(request, "notifications/settings.html", {
        "form": form,
        "devices": devices,
        "history": SentNotification.objects.filter(user=request.user)[:10],
        "sender": dict(zip(("last_run", "healthy"), sender_status())),
        "upcoming": upcoming_reminders(request.user, doctor=this_scope),
        "this_phone": devices, "this_scope": this_scope,
        "doctors": Doctor.objects.filter(is_active=True),
    })


@login_required
@require_POST
def set_scope(request):
    """'Remind me about': my own cases (default), a colleague's, or all cases of the practice."""
    value = request.POST.get("doctor", "")
    doctor = Doctor.objects.filter(pk=value).first() if value.isdigit() else None
    updated = PushSubscription.objects.filter(user=request.user).update(doctor=doctor)
    if updated:
        messages.success(request, f"You will get reminders for {doctor or 'all cases of the practice'}.")
    else:
        messages.warning(request, "Turn on notifications for this phone first.")
    return redirect("notifications:settings")


@csrf_exempt
def cron_run(request, token):
    """Hourly trigger for an external scheduler: /notifications/cron/<NOTIFICATIONS_CRON_TOKEN>/"""
    expected = getattr(settings, "NOTIFICATIONS_CRON_TOKEN", "")
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise Http404
    return JsonResponse({"ok": True, **run_scheduled()})


def _json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


@login_required
@require_POST
def subscribe(request):
    data = _json(request) or {}
    endpoint = str(data.get("endpoint", ""))
    keys = data.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        return HttpResponseBadRequest("Invalid subscription")
    sub, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user, "p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100],
            "device": request.META.get("HTTP_USER_AGENT", "")[:200], "failure_count": 0,
        },
    )
    if created:  # same choice as the user's other devices; default = own cases (staff: all cases)
        other = PushSubscription.objects.filter(user=request.user).exclude(pk=sub.pk).first()
        sub.doctor = other.doctor if other else request.user.doctor_profile
        sub.save(update_fields=["doctor"])
    return JsonResponse({"ok": True, "devices": PushSubscription.objects.filter(user=request.user).count()})


@login_required
@require_POST
def unsubscribe(request):
    data = _json(request) or {}
    PushSubscription.objects.filter(user=request.user, endpoint=str(data.get("endpoint", ""))).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def send_test(request):
    sent = notify(request.user, NotificationKind.TEST, "Test notification",
                  "Notifications are working on this device.", url="/notifications/")
    if sent:
        messages.success(request, f"Test notification sent to {sent} device(s).")
    else:
        messages.warning(request, "No device received it. Tap 'Turn on for this device' first.")
    return redirect("notifications:settings")


def vapid_public_key(request):
    return JsonResponse({"publicKey": public_key()})
