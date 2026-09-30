import pytest
from django.core.management import call_command
from core.models import Client, Pin, Source, User


@pytest.mark.django_db
def test_seed_repeatable_and_corpus(seeded):
    before = (Source.objects.count(), Pin.objects.count(), User.objects.count())
    call_command("seed")
    assert before == (Source.objects.count(), Pin.objects.count(), User.objects.count())
    assert Source.objects.filter(external_id__startswith="BE-").count() == 8
    assert Source.objects.get(external_id="BE-PAY-PROC-001").pins.get().status == "CONFIRMED"
    assert Source.objects.get(external_id="BE-PAY-CHK-2022").pins.get().status == "NEEDS_REVIEW"
    assert Source.objects.get(external_id="TELEWORK-PC200").pins.count() == 9
    assert Client.objects.count() == 6
    for pin in Pin.objects.all():
        assert pin.version.content.count(pin.quote) == 1
