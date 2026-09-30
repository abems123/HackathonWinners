from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(str, Enum):
    CONFLICT = "CONFLICT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNCERTAIN = "UNCERTAIN"
    CONFIRMED = "CONFIRMED"


ORANGE_KINDS = frozenset(
    {
        "SOURCE_CHANGED",
        "CONTEXT_CHANGED",
        "PROFILE_CHANGED",
        "EXPIRED",
        "AI_SUGGESTED",
        "POSSIBLE_CONFLICT",
        "SOURCE_OUTDATED",
    }
)


@dataclass(frozen=True)
class PinFacts:
    origin: str
    scope_type: str
    confirmed_version_id: int | None
    latest_version_id: int | None
    version_effective_to: datetime | None
    valid_until: datetime | None
    confirmed_profile_version: int | None
    client_profile_version: int | None
    passage_hash: str
    base: "PinFacts | None" = None
    base_passage_hash: str | None = None
    base_doubts: frozenset = frozenset()


def own_assumptions_hold(pin, now):
    return (
        pin.origin == "HUMAN"
        and pin.confirmed_version_id is not None
        and pin.confirmed_version_id == pin.latest_version_id
        and (pin.valid_until is None or pin.valid_until > now)
        and (pin.version_effective_to is None or pin.version_effective_to > now)
        and (
            pin.scope_type == "LAYER" or pin.confirmed_profile_version == pin.client_profile_version
        )
    )


def pin_status(pin, open_doubt_kinds, now):
    if "CONFLICT" in open_doubt_kinds:
        return Status.CONFLICT
    if open_doubt_kinds & ORANGE_KINDS or not own_assumptions_hold(pin, now):
        return Status.NEEDS_REVIEW
    if pin.base is not None:
        if (
            pin_status(pin.base, pin.base_doubts, now) != Status.CONFIRMED
            or pin.base.passage_hash != pin.base_passage_hash
        ):
            return Status.NEEDS_REVIEW
    if "QUESTION" in open_doubt_kinds:
        return Status.UNCERTAIN
    return Status.CONFIRMED
