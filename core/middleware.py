ADMIN_VIEW_SESSION_KEY = "admin_view"


class AdminViewMiddleware:
    """Turns on the admin view for users who chose "View as admin" in the profile menu."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and request.session.get(ADMIN_VIEW_SESSION_KEY):
            user.admin_view = True
        return self.get_response(request)
