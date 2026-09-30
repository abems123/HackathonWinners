from django.db import transaction
from django.utils import timezone

from core import authz
from core.ai.tasks import compare_claims, extract_claims
from core.audit import record
from core.domain.scope import matches
from core.domain.status import own_assumptions_hold
from core.engine.invalidate import create_doubt


def same_scope(a, b):
    if a.topic_id != b.topic_id:
        return False
    if a.client_id and b.client_id:
        return a.client_id == b.client_id
    if a.client_id:
        return matches(b.layer.scope_rule, a.client.profile)
    if b.client_id:
        return matches(a.layer.scope_rule, b.client.profile)
    return all(a.layer.scope_rule.get(k, v) == v for k, v in b.layer.scope_rule.items())


@transaction.atomic
def attach_conflict(a, b, provenance):
    # Check assumptions independently of AI's verdict. AI can only add doubts.
    now = timezone.now()
    holds_a = own_assumptions_hold(a.facts(), now)
    holds_b = own_assumptions_hold(b.facts(), now)
    targets = [a, b] if holds_a == holds_b else [b if holds_a else a]
    for pin in targets:
        other = b if pin.pk == a.pk else a
        label = "Demo AI fixture (unverified)" if provenance == "fixture" else "Possible contradiction · AI (unverified)"
        create_doubt(pin, "POSSIBLE_CONFLICT", f"Evidence comparison flagged incompatible claims with passage {other.pk}. A human must review them.", other, ai_label=label)
    return len(targets)


def review_source(user, source):
    authz.require(authz.can_upload_version(user, source))
    pins = list(source.pins.filter(superseded_by__isnull=True, excluded=False))
    candidates = list(authz.pins_for(user).filter(superseded_by__isnull=True, excluded=False).exclude(source=source))
    results, compared, flagged = [], 0, 0
    for pin in pins:
        claims, provenance = extract_claims(pin.quote)
        results.append({"pin": pin, "claims": claims, "provenance": provenance})
        if provenance == "invalid":
            create_doubt(pin, "AI_SUGGESTED", "The structured evidence check was invalid. Review manually; no AI label was applied.")
        for other in candidates:
            if not same_scope(pin, other):
                continue
            result, comparison_provenance = compare_claims(pin.quote, other.quote)
            if result is None:
                if comparison_provenance == "invalid":
                    create_doubt(pin, "AI_SUGGESTED", "The evidence comparison was invalid. Review manually; no AI label was applied.")
                continue
            compared += 1
            if result.relation == "CONTRADICTS":
                flagged += attach_conflict(pin, other, comparison_provenance)
    record(user, "AI_EVIDENCE_CHECK", f"Structured checks: {compared} comparisons, {flagged} review attachments. No confirmations or resolutions.", source=source)
    return {"results": results, "compared": compared, "flagged": flagged}
