"""Demo-only auto-login: seeds the synthetic demo once and signs visitors in as lotte.

Enabled unless BRON_DEMO_AUTOLOGIN=false. Never enable on a database with real data.
"""
import logging

from django.conf import settings
from django.contrib.auth import login

logger = logging.getLogger(__name__)
_seeded = False
SKIP = ("/static/", "/admin/", "/login/", "/logout/")


def ensure_demo_seed():
    global _seeded
    if _seeded:
        return
    from django.core.management import call_command

    from .models import User

    if not User.objects.filter(username="lotte").exists():
        try:
            call_command("seed")
        except Exception:  # a parallel worker may be seeding at the same moment
            logger.exception("Demo seed failed or ran concurrently")
    _seeded = User.objects.filter(username="lotte").exists()


class DemoAutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DEMO_AUTOLOGIN", False) and not request.path.startswith(
            ("/static/",)
        ):
            ensure_demo_seed()
            if not request.user.is_authenticated and not request.path.startswith(SKIP):
                from .models import User

                user = User.objects.filter(username="lotte", is_active=True).first()
                if user:
                    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)
