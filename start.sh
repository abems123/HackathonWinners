#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
# Demo deployment: create the fictional demo accounts shown on the login page.
# Idempotent: skips when data already exists. Set SEED_DEMO=false for real data.
if [ "${SEED_DEMO:-true}" = "true" ]; then
    python manage.py seed
fi
exec python -m gunicorn bron.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --access-logfile - --error-logfile -
