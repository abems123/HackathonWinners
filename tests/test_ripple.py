from datetime import datetime, timezone

import pytest
from django.conf import settings
from core.engine.reanchor import reanchor
from core.engine.sensitive import severity
from core.management.commands.seed import read_markdown
from core.models import Doubt, Source, User
from core.services.ripple import upload_version, sweep_expired


def test_reanchor_outcomes():
    quote = "The allowance is EUR 148.73 per month."
    assert reanchor("", quote, "", "Heading\n\n" + quote).outcome == "UNCHANGED"
    assert reanchor("", quote, "", quote + " Except for PC 124.").outcome == "CONTEXT_CHANGED"
    assert reanchor("", quote, "", quote + "\n\n" + quote).outcome == "AMBIGUOUS"
    assert reanchor("", quote, "", quote.replace("148.73", "154.20")).outcome == "MODIFIED"
    assert reanchor("", quote, "", "Completely unrelated policy.").outcome == "DELETED"
    assert severity(quote, quote.replace("148.73", "154.20")) == 1


@pytest.mark.django_db
def test_real_ripple_and_repeat(seeded):
    source = Source.objects.get(external_id="TELEWORK-PC200")
    _, body = read_markdown(settings.BASE_DIR / "seed/sources/telework-v2.md")
    version, result = upload_version(
        User.objects.get(username="sarah"), source, body, datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    assert (result["unchanged"], result["modified"], result["exceptions"]) == (8, 1, 1)
    assert source.pins.filter(confirmed_version=version).count() == 8
    assert Doubt.objects.filter(kind="SOURCE_CHANGED").count() == 2
    exception = Source.objects.get(external_id="PEETERS-EXCEPTION").pins.get()
    assert exception.status == "NEEDS_REVIEW"
    _, repeat = upload_version(
        User.objects.get(username="sarah"), source, body, datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    assert repeat["duplicate"]
    assert Doubt.objects.filter(kind="SOURCE_CHANGED").count() == 2
    assert not Doubt.objects.filter(
        pin__client__name="Bakkerij Janssens", kind="SOURCE_CHANGED"
    ).exists()


@pytest.mark.django_db
def test_expiry_dedup_and_fallback(seeded):
    sweep_expired()
    count = Doubt.objects.count()
    sweep_expired()
    assert Doubt.objects.count() == count
    doubt = Source.objects.get(external_id="CORRECTION-V1").pins.get().doubts.get(kind="EXPIRED")
    assert doubt.assignee_user is None
    assert doubt.assignee_team is not None
