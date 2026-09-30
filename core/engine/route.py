from django.utils import timezone
from core.domain.scope import matches
from core.models import Client


def routing(pin, effective_from=None):
    owner = pin.source.owner
    assignment = {"assignee_user": owner} if owner.is_active and owner.role != "SYSTEM" else {
        "assignee_team": pin.layer.team if pin.layer_id else pin.client.consultants.first().team}
    floor = (effective_from or timezone.now()).date()
    clients = [pin.client] if pin.client_id else [c for c in Client.objects.all() if matches(pin.layer.scope_rule, c.profile)]
    dates = [c.payroll_close for c in clients if c.payroll_close >= floor]
    return {**assignment, "due_date": min(dates) if dates else None}
