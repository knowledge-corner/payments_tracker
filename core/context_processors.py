from .models import AppSettings


def app_context(request):
    ctx = {"APP_VERSION": "1.0.0"}
    ctx["app_settings"] = AppSettings.load()
    return ctx
