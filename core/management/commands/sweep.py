from django.core.management import BaseCommand
from core.services.ripple import sweep_expired


class Command(BaseCommand):
    help = "Create deduplicated reviews for expired pins."

    def handle(self, *args, **options):
        self.stdout.write(f"Checked {sweep_expired()} expired passages.")
