from .authz import queue_for


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    return {"queue_count": queue_for(request.user).count()}
