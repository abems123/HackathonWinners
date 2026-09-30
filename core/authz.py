from django.db.models import Q
from django.http import Http404

from .domain.scope import matches
from .models import Client, Doubt, Layer, Pin, Source


def human(user):
    return user.is_authenticated and user.is_active and user.role != "SYSTEM"


def clients_for(user):
    if not human(user) or user.role == "EXPERT":
        return Client.objects.none()
    if user.role == "ADMIN":
        return Client.objects.all()
    if user.role == "OWNER":
        rules = list(
            Layer.objects.filter(Q(owner=user) | Q(team_id=user.team_id)).values_list(
                "scope_rule", flat=True
            )
        )
        return Client.objects.filter(
            pk__in=[
                c.pk
                for c in Client.objects.all()
                if c.consultants.filter(pk=user.pk).exists()
                or any(matches(rule, c.profile) for rule in rules)
            ]
        )
    return Client.objects.filter(consultants=user)


def can_read_client(user, client):
    return clients_for(user).filter(pk=client.pk).exists()


def can_change_layer_pin(user, pin):
    layer = pin.layer
    return (
        human(user)
        and user.role in {"OWNER", "ADMIN"}
        and (user.role == "ADMIN" or layer.owner_id == user.pk or layer.team_id == user.team_id)
    )


def can_read_pin(user, pin):
    if not human(user) or user.role == "EXPERT":
        return False
    if pin.client_id:
        return can_read_client(user, pin.client)
    # Layer knowledge is shared across the organisation; client knowledge is private.
    return user.role in {"CONSULTANT", "OWNER", "ADMIN"}


def can_change_pin(user, pin):
    return can_read_pin(user, pin) and (can_change_layer_pin(user, pin) if pin.layer_id else True)


def can_read_source(user, source):
    if not human(user) or user.role == "EXPERT":
        return False
    if source.client_id:
        return can_read_client(user, source.client)
    return user.role in {"CONSULTANT", "OWNER", "ADMIN"}


def can_upload_version(user, source):
    if not can_read_source(user, source):
        return False
    if source.client_id:
        return user.role in {"CONSULTANT", "OWNER", "ADMIN"}
    return user.role in {"OWNER", "ADMIN"} and (
        user.role == "ADMIN"
        or source.layer.owner_id == user.pk
        or source.layer.team_id == user.team_id
    )


def can_read_doubt(user, doubt):
    if doubt.kind == "QUESTION" and doubt.assignee_user_id == user.pk and human(user):
        return True
    return can_read_pin(user, doubt.pin)


def can_resolve_doubt(user, doubt):
    if human(user) and doubt.kind == "QUESTION" and doubt.assignee_user_id == user.pk:
        return True
    if user.role == "EXPERT":
        return False
    return can_change_pin(user, doubt.pin)


def pins_for(user):
    return Pin.objects.filter(
        pk__in=[
            p.pk for p in Pin.objects.select_related("layer", "client") if can_read_pin(user, p)
        ]
    )


def sources_for(user):
    return Source.objects.filter(
        pk__in=[
            s.pk
            for s in Source.objects.select_related("layer", "client")
            if can_read_source(user, s)
        ]
    )


def queue_for(user):
    assigned = Doubt.objects.filter(status="OPEN").filter(
        Q(assignee_user=user) | Q(assignee_team_id=user.team_id, assignee_team__isnull=False)
    )
    return assigned.filter(pk__in=[d.pk for d in assigned if can_read_doubt(user, d)])


def require(allowed):
    if not allowed:
        raise Http404("Not found")
