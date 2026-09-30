from unittest.mock import patch

import pytest
from django.urls import reverse

from core.ai.cache import FIXTURE_MODEL, cache_key
from core.ai.schemas import Claims, Comparison
from core.ai.tasks import compare_claims, extract_claims
from core.models import AiCache, Doubt, Source, User
from core.services.ai_review import attach_conflict, review_source, same_scope

pytestmark = pytest.mark.django_db


def test_quote_guard_and_invalid_comparison():
    with patch(
        "core.ai.client.request",
        return_value=(
            Claims(
                claims=[
                    {"quote": "invented 500 EUR", "subject": "amount", "value": "500"},
                    {"quote": "100 EUR", "subject": "amount", "value": "100"},
                ]
            ),
            "live",
        ),
    ):
        claims, _ = extract_claims("The allowance is 100 EUR.")
        assert [c.quote for c in claims] == ["100 EUR"]
    with patch(
        "core.ai.client.request",
        return_value=(
            Comparison(relation="CONTRADICTS", quote_a="fake", quote_b="also fake"),
            "live",
        ),
    ):
        result, provenance = compare_claims("100 EUR", "120 EUR")
        assert result is None and provenance == "invalid"


def test_cache_key_changes_with_model_prompt_and_input():
    key = cache_key("extract_claims", "model-a", "1", {"passage": "A"})
    assert key != cache_key("extract_claims", "model-b", "1", {"passage": "A"})
    assert key != cache_key("extract_claims", "model-a", "2", {"passage": "A"})
    assert key != cache_key("extract_claims", "model-a", "1", {"passage": "B"})


def test_offline_fixtures_require_no_network(seeded):
    pin = Source.objects.get(external_id="BE-PAY-PROC-001").pins.get()
    with patch("google.genai.Client", side_effect=AssertionError("Network must not be used")):
        claims, provenance = extract_claims(pin.quote)
    assert claims and provenance == "fixture"
    assert claims[0].quote in pin.quote
    assert AiCache.objects.filter(model=FIXTURE_MODEL).exists()


def test_invalid_response_adds_doubt_without_ai_label(seeded):
    source = Source.objects.get(external_id="CORRECTION-V3")
    with (
        patch("core.services.ai_review.extract_claims", return_value=([], "invalid")),
        patch("core.services.ai_review.compare_claims", return_value=(None, "unavailable")),
    ):
        review_source(User.objects.get(username="sarah"), source)
    doubt = source.pins.get().doubts.get(kind="AI_SUGGESTED")
    assert not doubt.ai_label
    assert source.pins.get().status == "NEEDS_REVIEW"


def test_asymmetric_conflict_attachment_and_scope(seeded):
    old = Source.objects.get(external_id="BE-PAY-CHK-2022").pins.get()
    current = Source.objects.get(external_id="BE-PAY-PROC-001").pins.get()
    nl = Source.objects.get(external_id="NL-PAY-PROC-001").pins.get()
    assert not same_scope(current, nl)
    attach_conflict(old, current, "fixture")
    assert current.status == "CONFIRMED"
    assert old.status == "NEEDS_REVIEW"
    owner = User.objects.get(username="sofie")
    result = review_source(owner, current.source)
    assert result["compared"] > 0
    assert current.status == "CONFIRMED"
    assert old.doubts.filter(kind="POSSIBLE_CONFLICT", status="OPEN").count() == 1


def test_ai_review_route_permissions(seeded, client):
    source = Source.objects.get(external_id="CORRECTION-V3")
    client.force_login(User.objects.get(username="lotte"))
    assert client.post(reverse("ai_review", args=[source.pk])).status_code == 404
    client.force_login(User.objects.get(username="sarah"))
    assert client.post(reverse("ai_review", args=[source.pk])).status_code == 200
    assert not Doubt.objects.filter(pin__source=source, kind="CONFLICT").exists()
