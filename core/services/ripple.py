import hashlib

from django.db import transaction
from django.utils import timezone

from core import authz
from core.audit import record
from core.domain.passage import normalize_newlines
from core.engine.invalidate import create_doubt
from core.engine.reanchor import reanchor
from core.engine.sensitive import severity
from core.models import Pin, Source, SourceVersion


@transaction.atomic
def upload_version(user, source, content, effective_from, effective_to=None):
    source = Source.objects.select_for_update().get(pk=source.pk)
    authz.require(authz.can_upload_version(user, source))
    content = normalize_newlines(content)
    digest = hashlib.sha256(content.encode()).hexdigest()
    existing = source.versions.filter(content_hash=digest).first()
    summary = {
        "unchanged": 0,
        "modified": 0,
        "exceptions": 0,
        "items": [],
        "duplicate": bool(existing),
    }
    if existing:
        return existing, summary
    latest = source.latest
    version = SourceVersion.objects.create(
        source=source,
        content=content,
        number=latest.number + 1,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    for pin in Pin.objects.select_for_update().filter(
        source=source, superseded_by__isnull=True, excluded=False
    ):
        result = reanchor(pin.prefix, pin.quote, pin.suffix, content)
        summary["items"].append(
            {"pin": pin, "outcome": result.outcome, "before": pin.quote, "after": result.quote}
        )
        if result.outcome == "UNCHANGED":
            # Carry only an existing human confirmation, never create one from nothing.
            old_version_id = pin.version_id
            pin.version = version
            pin.prefix, pin.quote, pin.suffix = result.prefix, result.quote, result.suffix
            if pin.origin == "HUMAN" and pin.confirmed_version_id == old_version_id:
                pin.confirmed_version = version
            pin.save()
            record(
                None,
                "AUTO_CARRIED",
                f"Unchanged passage carried to v{version.number}; original human confirmation retained.",
                pin=pin,
            )
            summary["unchanged"] += 1
        else:
            summary["modified"] += 1
            kind = "CONTEXT_CHANGED" if result.outcome == "CONTEXT_CHANGED" else "SOURCE_CHANGED"
            from core.ai.tasks import triage_change

            triage, provenance = triage_change(pin.quote, result.quote)
            label = ""
            if triage:
                prefix = "Demo AI fixture" if provenance == "fixture" else "AI"
                label = f"{prefix} (unverified): {triage.label.replace('_', ' ').lower()}"
            create_doubt(
                pin,
                kind,
                f"v{version.number}: passage {result.outcome.lower().replace('_', ' ')}. Review the latest text.",
                severity=severity(pin.quote, result.quote),
                effective_from=effective_from,
                ai_label=label,
            )
            for exception in pin.exceptions.filter(superseded_by__isnull=True, excluded=False):
                create_doubt(
                    exception,
                    "SOURCE_CHANGED",
                    "The base passage changed; check the client-specific exception.",
                    severity=1,
                    effective_from=effective_from,
                )
                summary["exceptions"] += 1
    record(
        user,
        "SOURCE_UPLOADED",
        f"v{version.number}: {summary['unchanged']} unchanged, {summary['modified']} modified, {summary['exceptions']} exceptions to review.",
        source=source,
    )
    return version, summary


def sweep_expired():
    count = 0
    now = timezone.now()
    for pin in Pin.objects.filter(superseded_by__isnull=True, excluded=False):
        if (pin.valid_until and pin.valid_until <= now) or (
            pin.version.effective_to and pin.version.effective_to <= now
        ):
            create_doubt(pin, "EXPIRED", "The passage or its source has passed its review expiry.")
            count += 1
    return count
