import pytest
from core import authz
from core.models import Client, Source, User

pytestmark = pytest.mark.django_db


def test_object_permissions(seeded):
    pieter = User.objects.get(username="pieter")
    lotte = User.objects.get(username="lotte")
    sarah = User.objects.get(username="sarah")
    assert not authz.can_read_client(pieter, Client.objects.get(name="Bakkerij Janssens"))
    pin = Source.objects.get(external_id="CORRECTION-V1").pins.get()
    assert authz.can_read_pin(lotte, pin)
    assert not authz.can_change_pin(lotte, pin)
    assert authz.can_change_pin(sarah, pin)
    assert not authz.can_read_pin(User.objects.get(username="anne"), pin)
    assert not authz.can_change_pin(User.objects.get(username="system"), pin)
