import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from core.ai import client
from core.ai.cache import FIXTURE_MODEL
from core.ai.schemas import Claims, Comparison, Triage
from core.models import AiCache


class Command(BaseCommand):
    help = "Generate real Vertex model outputs for all demo fixture inputs using ADC."

    def handle(self, *args, **options):
        if settings.AI_MODE != "live" or client.model_name() == FIXTURE_MODEL:
            raise CommandError(
                "Set AI_MODE=live, GCP_PROJECT and GEMINI_MODEL and configure ADC first."
            )
        path = settings.BASE_DIR / "seed/ai-cache.json"
        entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
        schemas = {"extract_claims": Claims, "compare_claims": Comparison, "triage_change": Triage}
        generated = []
        for entry in entries:
            result, provenance = client.request(
                entry["task"], entry["input"], schemas[entry["task"]]
            )
            if result is None or provenance not in {"live", "cache"}:
                raise CommandError(
                    f"Model failed on {entry['task']}; the checked-in fixture file was not changed."
                )
            row = AiCache.objects.get(
                key=client.cache_key(
                    entry["task"],
                    client.model_name(),
                    client.prompt_version(entry["task"]),
                    entry["input"],
                )
            )
            generated.append(
                {
                    "key": row.key,
                    "task": row.task,
                    "model": row.model,
                    "prompt_version": row.prompt_version,
                    "input": entry["input"],
                    "output": row.output,
                }
            )
        path.write_text(
            json.dumps(
                {"provenance": "Vertex AI outputs; human-unverified", "entries": generated},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.stdout.write(f"Generated {len(generated)} cached model outputs.")
