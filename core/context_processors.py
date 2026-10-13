from .assets import asset_version
from .models import AppSettings


def app_context(request):
    ctx = {"APP_VERSION": "1.0.0", "ASSET_V": asset_version()}
    ctx["app_settings"] = AppSettings.load()
    return ctx
