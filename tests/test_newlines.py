from datetime import datetime, timezone

import pytest
from django.conf import settings

from core.forms import UploadForm
from core.management.commands.seed import read_markdown
from core.models import Source, User
from core.services.ripple import upload_version


@pytest.mark.django_db
def test_crlf_upload_matches_lf_ripple(seeded):
    """Browsers post textareas with CRLF; the telework ripple must stay 8/1/1."""
    _, body = read_markdown(settings.BASE_DIR / "seed/sources/telework-v2.md")
    form = UploadForm(
        {"content": body.replace("\n", "\r\n"), "effective_from": "2027-01-01T00:00"}
    )
    assert form.is_valid(), form.errors
    assert "\r" not in form.cleaned_data["content"]
    source = Source.objects.get(external_id="TELEWORK-PC200")
    _, result = upload_version(
        User.objects.get(username="sarah"),
        source,
        form.cleaned_data["content"],
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    assert (result["unchanged"], result["modified"], result["exceptions"]) == (8, 1, 1)
