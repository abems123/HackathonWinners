#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
exec python -m gunicorn bron.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --access-logfile - --error-logfile -
