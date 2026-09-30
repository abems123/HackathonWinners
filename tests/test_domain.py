from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from core.domain.passage import anchor, passage_hash
from core.domain.scope import matches
from core.domain.status import ORANGE_KINDS, PinFacts, Status, pin_status

NOW = datetime.now(timezone.utc)
GOOD = PinFacts("HUMAN", "LAYER", 1, 1, None, None, None, None, "abc")


@pytest.mark.parametrize("kind", sorted(ORANGE_KINDS))
def test_orange_kinds(kind):
    assert pin_status(GOOD, {kind}, NOW) == Status.NEEDS_REVIEW


@pytest.mark.parametrize("change", [
    {"origin": "AI_SUGGESTED"}, {"confirmed_version_id": None}, {"latest_version_id": 2},
    {"valid_until": NOW}, {"version_effective_to": NOW - timedelta(days=1)},
    {"scope_type": "CLIENT", "confirmed_profile_version": 1, "client_profile_version": 2},
])
def test_broken_assumption_precedes_question(change):
    assert pin_status(replace(GOOD, **change), {"QUESTION"}, NOW) == Status.NEEDS_REVIEW


def test_precedence_and_dependency():
    assert pin_status(GOOD, set(), NOW) == Status.CONFIRMED
    assert pin_status(GOOD, {"QUESTION"}, NOW) == Status.UNCERTAIN
    assert pin_status(GOOD, {"CONFLICT", "SOURCE_CHANGED"}, NOW) == Status.CONFLICT
    exception = replace(GOOD, base=GOOD, base_passage_hash="abc")
    assert pin_status(exception, set(), NOW) == Status.CONFIRMED
    assert pin_status(replace(exception, base_passage_hash="old"), set(), NOW) == Status.NEEDS_REVIEW
    assert pin_status(replace(exception, base=replace(GOOD, latest_version_id=2)), set(), NOW) == Status.NEEDS_REVIEW
    assert pin_status(replace(exception, base_doubts=frozenset({"CONFLICT"})), set(), NOW) == Status.NEEDS_REVIEW


def test_anchor_and_scope():
    assert passage_hash("a  b", "c", "d") == passage_hash("a b", "c", "d")
    assert anchor("Heading\n\nThe amount is 100.\n\nOther", "The amount is 100.") == ("", "The amount is 100.", "")
    with pytest.raises(ValueError):
        anchor("same same", "same")
    assert matches({"country": "BE"}, {"country": "BE", "pc": "200"})
    assert not matches({"country": "NL"}, {"country": "BE"})
