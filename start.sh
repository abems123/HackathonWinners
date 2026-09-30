#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
# Demo deployments need the synthetic accounts, otherwise nobody can sign in.
# The seed is idempotent (it never overwrites reviews). Never enable on real data.
if [ "${BRON_SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed
fi
exec python -m gunicorn bron.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --access-logfile - --error-logfile -
