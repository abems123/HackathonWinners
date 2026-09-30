import pytest
from django.test import Client as Browser
from django.urls import reverse

from core.engine.invalidate import create_doubt
from core.models import AuditEvent, Client, Pin, Source, Topic, User

pytestmark = pytest.mark.django_db


def test_pages_render_and_private_ids_404(seeded, client):
    client.force_login(User.objects.get(username="lotte"))
    for page in ["home", "clients", "queue", "sources", "activity", "people"]:
        assert client.get(reverse(page)).status_code == 200
    bakery = Client.objects.get(name="Bakkerij Janssens")
    assert client.get(reverse("client", args=[bakery.pk])).status_code == 200
    for topic in Topic.objects.all():
        assert client.get(reverse("topic", args=[bakery.pk, topic.slug])).status_code == 200
    for source in Source.objects.filter(client__isnull=True):
        assert client.get(reverse("source", args=[source.pk])).status_code == 200
    for pin in Pin.objects.filter(layer__isnull=False):
        assert client.get(reverse("pin", args=[pin.pk])).status_code == 200
    client.force_login(User.objects.get(username="pieter"))
    assert client.get(reverse("client", args=[bakery.pk])).status_code == 404
    assert client.get(reverse("profile", args=[bakery.pk])).status_code == 404
    private = Source.objects.get(external_id="PEETERS-EXCEPTION")
    assert client.get(reverse("source", args=[private.pk])).status_code == 404
    assert client.get(reverse("pin", args=[private.pins.get().pk])).status_code == 404


def test_csrf_and_post_only_mutations(seeded):
    browser = Browser(enforce_csrf_checks=True)
    browser.force_login(User.objects.get(username="sarah"))
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    assert browser.get(reverse("action", args=[pin.pk])).status_code == 405
    assert browser.post(reverse("action", args=[pin.pk]), {"action": "confirm", "reason": "Checked"}).status_code == 403


def test_question_view_does_not_expose_client(seeded, client):
    expert = User.objects.get(username="anne")
    pin = Source.objects.get(external_id="PEETERS-EXCEPTION").pins.get()
    doubt = create_doubt(pin, "QUESTION", "Can you verify the reimbursement?", assignee_user=expert, assignee_team=None)
    client.force_login(expert)
    page = client.get(reverse("doubt", args=[doubt.pk]))
    assert page.status_code == 200
    assert b"Can you verify the reimbursement?" in page.content
    # The exact source quote may name the client; no other client context or links are exposed.
    assert b"Garage Peeters \xc2\xb7 telework agreement" not in page.content
    assert reverse("client", args=[pin.client_id]).encode() not in page.content
    assert client.get(reverse("client", args=[pin.client_id])).status_code == 404
    assert client.get(reverse("source", args=[pin.source_id])).status_code == 404


def test_consultant_action_options_and_htmx(seeded, client):
    client.force_login(User.objects.get(username="lotte"))
    pin = Source.objects.get(external_id="CORRECTION-V3").pins.get()
    page = client.get(reverse("pin", args=[pin.pk]))
    assert b'value="confirm"' not in page.content
    response = client.post(reverse("action", args=[pin.pk]), {"action": "source_outdated", "reason": "Please recheck"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == reverse("pin", args=[pin.pk])
    assert AuditEvent.objects.filter(action="SOURCE_OUTDATED").exists()


def test_knowledge_gap_and_wrong_country(seeded, client):
    client.force_login(User.objects.get(username="lotte"))
    lu = Client.objects.get(name="Maison Laurent")
    response = client.get(reverse("topic", args=[lu.pk, "payroll-input"]))
    assert "Anne Muller" in response.content.decode()
    assert len(response.context["pins"]) == 0
    assert response.context["excluded"]
    be = Client.objects.get(name="Bakkerij Janssens")
    response = client.get(reverse("topic", args=[be.pk, "payroll-input"]))
    assert any(p.source.external_id == "NL-PAY-PROC-001" for p in response.context["excluded"])
    assert not any(p.client_id for p in response.context["pins"])


def test_upload_and_profile_routes(seeded, client):
    source = Source.objects.get(external_id="TELEWORK-PC200")
    client.force_login(User.objects.get(username="lotte"))
    assert client.get(reverse("upload", args=[source.pk])).status_code == 404
    client.force_login(User.objects.get(username="sarah"))
    assert client.get(reverse("upload", args=[source.pk])).status_code == 200
    assert client.get(reverse("profile", args=[Client.objects.get(name="Garage Peeters").pk])).status_code == 200
