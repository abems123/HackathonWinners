from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core import authz
from core.audit import record
from core.domain.passage import anchor
from core.engine.invalidate import create_doubt
from core.models import Client, Pin, Source, SourceVersion

DISMISSIBLE = {"QUESTION", "AI_SUGGESTED", "POSSIBLE_CONFLICT", "SOURCE_OUTDATED"}


def close(doubts, reason):
    doubts.update(status="RESOLVED", resolution=reason, resolved_at=timezone.now())


@transaction.atomic
def perform(user, pin, action, reason, *, doubt=None, version_id=None, quote="", related_pin=None, expert=None, valid_until=None, client=None):
    pin = Pin.objects.select_for_update().get(pk=pin.pk)
    authz.require(authz.human(user))
    if doubt is not None:
        doubt = pin.doubts.select_for_update().get(pk=doubt.pk)
        if doubt.status != "OPEN":
            raise ValidationError("This review is already resolved. Refresh the page.")
    if not reason.strip():
        raise ValidationError("A reason is required.")
    if action == "answer":
        authz.require(doubt is not None and doubt.kind == "QUESTION" and authz.can_resolve_doubt(user, doubt))
        close(pin.doubts.filter(pk=doubt.pk), reason)
    else:
        authz.require(authz.can_read_pin(user, pin))
        if action not in {"ask", "source_outdated", "add_exception"}:
            authz.require(authz.can_change_pin(user, pin))
        if action == "confirm":
            latest = pin.source.latest
            if version_id != latest.pk:
                raise ValidationError("The source has changed. Review its latest version before confirming.")
            if pin.open_kinds & {"CONFLICT", "POSSIBLE_CONFLICT", "QUESTION"}:
                raise ValidationError("Resolve the conflict or open question before confirming this passage.")
            if pin.superseded_by_id or pin.excluded:
                raise ValidationError("A superseded or excluded pin cannot be confirmed.")
            if latest.effective_to and latest.effective_to <= timezone.now():
                raise ValidationError("This source version has expired. Upload a valid version first.")
            if pin.valid_until and pin.valid_until <= timezone.now() and not valid_until:
                raise ValidationError("Set a new future review date for this expired pin.")
            if valid_until and valid_until <= timezone.now():
                raise ValidationError("The review date must be in the future.")
            if pin.base_id and pin.base.status != "CONFIRMED":
                raise ValidationError("Resolve the base passage before confirming its exception.")
            try:
                pin.prefix, pin.quote, pin.suffix = anchor(latest.content, quote or pin.quote)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            pin.version = latest
            pin.confirmed_version = latest
            pin.confirmed_by = user
            pin.confirmed_at = timezone.now()
            pin.origin = "HUMAN"
            if valid_until:
                pin.valid_until = valid_until
            if pin.client_id:
                pin.confirmed_profile_version = pin.client.profile_version
            if pin.base_id:
                pin.base_passage_hash = pin.base.passage_hash
            pin.save()
            close(pin.doubts.filter(status="OPEN"), reason)
        elif action == "supersede":
            authz.require(related_pin is not None and authz.can_read_pin(user, related_pin))
            if (related_pin.pk == pin.pk or related_pin.topic_id != pin.topic_id or
                related_pin.layer_id != pin.layer_id or related_pin.client_id != pin.client_id or
                related_pin.status != "CONFIRMED" or related_pin.superseded_by_id or related_pin.excluded):
                raise ValidationError("Choose a confirmed active replacement in the same topic and scope.")
            pin.superseded_by = related_pin
            pin.save()
            close(pin.doubts.filter(status="OPEN"), reason)
            for exception in pin.exceptions.all():
                create_doubt(exception, "SOURCE_CHANGED", "The base pin was superseded; review this exception.")
        elif action == "does_not_apply":
            if pin.layer_id:
                raise ValidationError("Only client-specific pins can be marked not applicable.")
            pin.excluded = True
            pin.save()
            close(pin.doubts.filter(status="OPEN"), reason)
        elif action == "dismiss":
            if doubt is None or doubt.kind not in DISMISSIBLE:
                raise ValidationError("This doubt cannot be dismissed. Review its underlying assumptions.")
            close(pin.doubts.filter(pk=doubt.pk), reason)
        elif action == "escalate":
            if doubt is None or doubt.kind != "POSSIBLE_CONFLICT":
                raise ValidationError("Only a possible conflict can be escalated.")
            close(pin.doubts.filter(pk=doubt.pk), reason)
            create_doubt(pin, "CONFLICT", reason, doubt.related_pin, severity=1)
        elif action == "ask":
            if expert is None or not expert.is_active or expert.role == "SYSTEM":
                raise ValidationError("Select an active person to ask.")
            create_doubt(pin, "QUESTION", reason, assignee_user=expert, assignee_team=None)
        elif action == "source_outdated":
            create_doubt(pin, "SOURCE_OUTDATED", reason)
        elif action == "add_exception":
            authz.require(client is not None and authz.can_read_client(user, client))
            from core.domain.scope import matches
            if pin.client_id or not matches(pin.layer.scope_rule, client.profile):
                raise ValidationError("An exception must reference a layer inherited by this client.")
            if not quote.strip():
                raise ValidationError("Provide the client-specific agreement text.")
            if valid_until and valid_until <= timezone.now():
                raise ValidationError("The exception expiry must be in the future.")
            source = Source.objects.create(title=f"{client.name} · {pin.topic.name} exception", owner=user, client=client, type="Client agreement")
            source.topics.add(pin.topic)
            version = SourceVersion.objects.create(source=source, number=1, content=quote)
            exception = Pin.objects.create(title=f"Client exception · {pin.topic.name}", topic=pin.topic, source=source,
                version=version, client=client, quote=quote, base=pin, base_passage_hash=pin.passage_hash,
                origin="HUMAN", valid_until=valid_until)
            create_doubt(exception, "SOURCE_CHANGED", "New exception requires human confirmation against its source and base.")
            record(user, action.upper(), reason, pin=exception, client=client)
        else:
            raise ValidationError("Unknown action.")
    record(user, action.upper(), reason, pin=pin)
    return pin


@transaction.atomic
def update_profile(user, client, profile, payroll_close, reason):
    client = Client.objects.select_for_update().get(pk=client.pk)
    authz.require(authz.can_read_client(user, client) and authz.human(user))
    changed = client.profile != profile
    client.profile = profile
    client.payroll_close = payroll_close
    if changed:
        client.profile_version += 1
    client.save()
    if changed:
        for pin in Pin.objects.filter(client=client, superseded_by__isnull=True, excluded=False):
            create_doubt(pin, "PROFILE_CHANGED", "The client's country or joint committee changed.")
    record(user, "PROFILE_CHANGED", reason, client=client)
