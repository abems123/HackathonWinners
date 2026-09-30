import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.engine.invalidate import create_doubt
from core.models import AuditEvent, Client, Source, User
from core.services.actions import perform, update_profile

pytestmark = pytest.mark.django_db


def test_assigned_owner_can_answer_question(seeded, client):
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    owner = User.objects.get(username="sarah")
    question = create_doubt(pin, "QUESTION", "Please clarify this deadline", assignee_user=owner, assignee_team=None)
    client.force_login(owner)
    page = client.get(reverse("doubt", args=[question.pk]))
    assert b'value="answer"' in page.content
    response = client.post(reverse("action", args=[pin.pk]), {"action": "answer", "reason": "The current deadline is the 25th.", "doubt_id": question.pk})
    assert response.status_code == 302
    question.refresh_from_db()
    assert question.status == "RESOLVED"


def test_profile_change_invalidates_client_confirmation(seeded):
    user = User.objects.get(username="lotte")
    client = Client.objects.get(name="Garage Peeters")
    pin = Source.objects.get(external_id="PEETERS-EXCEPTION").pins.get()
    assert pin.status == "CONFIRMED"
    update_profile(user, client, {"country": "BE", "pc": "124"}, client.payroll_close, "New sector")
    pin.refresh_from_db()
    assert pin.status == "NEEDS_REVIEW"
    assert pin.doubts.get(kind="PROFILE_CHANGED").status == "OPEN"


def test_new_exception_needs_explicit_confirmation(seeded):
    user = User.objects.get(username="lotte")
    client = Client.objects.get(name="Bakkerij Janssens")
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    perform(user, pin, "add_exception", "Written client agreement", client=client, quote="Bakkerij corrections are due by the 22nd.")
    exception = pin.exceptions.get(client=client)
    assert exception.status == "NEEDS_REVIEW"
    assert exception.confirmed_by_id is None
    perform(user, exception, "confirm", "Agreement verified", version_id=exception.version_id)
    exception.refresh_from_db()
    assert exception.status == "CONFIRMED"


def test_base_supersession_fails_safe_even_without_ripple_doubt(seeded):
    exception = Source.objects.get(external_id="PEETERS-EXCEPTION").pins.get()
    base = exception.base
    base.excluded = True
    base.save()
    assert exception.status == "NEEDS_REVIEW"


def test_audit_cannot_be_edited_or_deleted(seeded):
    event = AuditEvent.objects.first()
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).update(detail="Changed")
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).delete()
