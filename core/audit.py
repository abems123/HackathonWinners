from .models import AuditEvent


def record(actor, action, detail, pin=None, source=None, client=None):
    return AuditEvent.objects.create(
        actor=actor, action=action, detail=detail, pin=pin, source=source, client=client
    )
