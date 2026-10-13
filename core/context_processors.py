from . import practice
from .assets import asset_version
from .models import AppSettings


def app_context(request):
    ctx = {"APP_VERSION": "1.0.0", "ASSET_V": asset_version()}
    ctx["app_settings"] = AppSettings.load()
    user = getattr(request, "user", None)
    ctx["is_practice_session"] = bool(user and practice.is_practice_session(user))
    ctx["device_doctor"] = practice.device_doctor(request) if ctx["is_practice_session"] else None
    return ctx
