import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-abcdefghijklmnopqrstuvwxyz-123456789")
os.environ["DJANGO_DEBUG"] = "True"
os.environ["DJANGO_HTTPS"] = "False"
from .settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
