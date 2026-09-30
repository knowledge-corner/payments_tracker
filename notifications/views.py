import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import NotificationPreferenceForm
from .models import NotificationKind, NotificationPreference, PushSubscription, SentNotification
from .push import notify, public_key


@login_required
def settings_page(request):
    prefs = NotificationPreference.for_user(request.user)
    form = NotificationPreferenceForm(request.POST or None, instance=prefs)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Notification settings saved.")
        return redirect("notifications:settings")
    return render(request, "notifications/settings.html", {
        "form": form,
        "devices": PushSubscription.objects.filter(user=request.user),
        "history": SentNotification.objects.filter(user=request.user)[:10],
    })


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
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user, "p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100],
            "device": request.META.get("HTTP_USER_AGENT", "")[:200], "failure_count": 0,
        },
    )
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
