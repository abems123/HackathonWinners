from core.models import Doubt
from .route import routing


def create_doubt(pin, kind, reason, related=None, severity=2, effective_from=None, **extra):
    values = {**routing(pin, effective_from), "reason": reason, "severity": severity, **extra}
    if kind == "QUESTION":
        return Doubt.objects.create(pin=pin, kind=kind, **values)
    key = f"{kind}:{pin.pk}:{related.pk if related else ''}"
    doubt, _ = Doubt.objects.get_or_create(
        dedupe_key=key,
        status="OPEN",
        defaults={"pin": pin, "kind": kind, "related_pin": related, **values},
    )
    return doubt
