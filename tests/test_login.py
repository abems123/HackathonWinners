import pytest
from django.urls import reverse

DEMO_PASSWORD = "Bron-demo-2026!"


@pytest.mark.django_db
def test_demo_login_with_real_csrf(seeded, client):
    csrf_client = client.__class__(enforce_csrf_checks=True)
    page = csrf_client.get(reverse("login"))
    assert page.status_code == 200
    token = page.cookies["csrftoken"].value
    response = csrf_client.post(
        reverse("login"),
        {"username": "lotte", "password": DEMO_PASSWORD, "csrfmiddlewaretoken": token},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert csrf_client.get(reverse("home")).status_code == 200


@pytest.mark.django_db
def test_wrong_password_and_system_account_rejected(seeded, client):
    for username, password in [("lotte", "wrong"), ("system", DEMO_PASSWORD)]:
        response = client.post(reverse("login"), {"username": username, "password": password})
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_next_rejects_external_redirect(seeded, client):
    response = client.post(
        reverse("login") + "?next=https://evil.example/",
        {"username": "lotte", "password": DEMO_PASSWORD, "next": "https://evil.example/"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.django_db
def test_malformed_doubt_id_is_404_not_500(seeded, client):
    from core.models import Pin, User

    client.force_login(User.objects.get(username="sarah"))
    pin = Pin.objects.filter(layer__isnull=False).first()
    response = client.post(
        reverse("action", args=[pin.pk]), {"doubt_id": "abc", "action": "ask", "reason": "x"}
    )
    assert response.status_code == 404
