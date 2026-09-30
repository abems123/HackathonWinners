import pytest
from django.core.exceptions import ValidationError
from django.http import Http404
from core.engine.invalidate import create_doubt
from core.models import AuditEvent, Source, User
from core.services.actions import perform

pytestmark = pytest.mark.django_db


def test_consultant_can_flag_but_not_confirm(seeded):
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    lotte = User.objects.get(username="lotte")
    perform(lotte, pin, "source_outdated", "Please verify this procedure.")
    assert pin.status == "NEEDS_REVIEW"
    with pytest.raises(Http404):
        perform(lotte, pin, "confirm", "Checked", version_id=pin.version_id)
    assert AuditEvent.objects.filter(action="SOURCE_OUTDATED").exists()


def test_confirm_and_stale_version_guard(seeded):
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    sarah = User.objects.get(username="sarah")
    with pytest.raises(ValidationError):
        perform(sarah, pin, "confirm", "Checked", version_id=-1)
    perform(sarah, pin, "confirm", "Verified against the latest source", version_id=pin.version_id)
    assert pin.status == "CONFIRMED"
    with pytest.raises(Http404):
        perform(User.objects.get(username="system"), pin, "confirm", "Checked", version_id=pin.version_id)


def test_dismiss_escalate_and_supersede(seeded):
    old = Source.objects.get(external_id="CORRECTION-V1").pins.get()
    new = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    sarah = User.objects.get(username="sarah")
    with pytest.raises(ValidationError):
        perform(sarah, old, "dismiss", "Ignore", doubt=old.doubts.get(kind="EXPIRED"))
    perform(sarah, old, "escalate", "Confirmed contradictory deadlines", doubt=old.doubts.get(kind="POSSIBLE_CONFLICT"))
    assert old.status == "CONFLICT"
    perform(sarah, old, "supersede", "Replaced by current instructions", related_pin=new)
    old.refresh_from_db()
    assert old.superseded_by == new
    assert not old.doubts.filter(status="OPEN").exists()


def test_expert_has_question_only_access(seeded):
    from core import authz
    pin = Source.objects.get(external_id="PEETERS-EXCEPTION").pins.get()
    expert = User.objects.get(username="anne")
    question = create_doubt(pin, "QUESTION", "Please check this passage", assignee_user=expert, assignee_team=None)
    assert authz.can_read_doubt(expert, question)
    assert not authz.can_read_client(expert, pin.client)
    perform(expert, pin, "answer", "Please refer this to the Belgian team.", doubt=question)
    question.refresh_from_db()
    assert question.status == "RESOLVED"
