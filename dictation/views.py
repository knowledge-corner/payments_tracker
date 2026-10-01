import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import Doctor
from hospitals.views import my_hospital_ids

from .parser import parse


@login_required
@require_POST
def parse_view(request):
    """Dictated text -> suggested Add Case field values (JSON). Nothing is saved here."""
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        payload = {}
    text = str(payload.get("text", ""))[:1000]
    doctor = request.user.doctor_profile
    if request.user.is_app_admin and str(payload.get("doctor", "")).isdigit():
        doctor = Doctor.objects.filter(pk=payload["doctor"]).first() or doctor
    result = parse(text, doctor, mine=my_hospital_ids(request))
    return JsonResponse(result.as_json(my_hospital_ids(request)))
