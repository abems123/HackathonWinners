import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-used-for-deployment-123456789")
os.environ.setdefault("DJANGO_DEBUG", "True")

import pytest
from django.core.management import call_command


@pytest.fixture
def seeded(db):
    call_command("seed")
