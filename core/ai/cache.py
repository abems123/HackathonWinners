import hashlib
import json

from django.conf import settings
from core.models import AiCache

FIXTURE_MODEL = "synthetic-demo-fixture-v1"


def prompt_version(task):
    prompt = (settings.BASE_DIR / "core/ai/prompts" / f"{task}.txt").read_text(encoding="utf-8")
    return "1-" + hashlib.sha256(prompt.encode()).hexdigest()[:12]


def cache_key(task, model, version, data):
    serialized = json.dumps([task, model, version, data], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def load_fixtures():
    path = settings.BASE_DIR / "seed/ai-cache.json"
    if not path.exists():
        return 0
    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    for row in entries:
        AiCache.objects.get_or_create(key=row["key"], defaults={k: row[k] for k in ("task", "model", "prompt_version", "output")})
    return len(entries)
