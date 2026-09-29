from .models import AppSettings


def app_context(request):
    ctx = {"APP_VERSION": "1.0.0"}
    if request.user.is_authenticated:
        ctx["app_settings"] = AppSettings.load()
    return ctx
