#!/usr/bin/env bash
set -e

case "$1" in
  web)
    # Schéma & assets (uniquement côté web)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    # Serveur web prod
    exec gunicorn rb_exchange.wsgi:application --bind 0.0.0.0:8000 --workers 3
    ;;
  worker)
    # Exécution des tâches
    # Par défaut: prefork (Linux). Pour Windows sans Docker: mettre CELERY_POOL=solo dans .env
    POOL="${CELERY_POOL:-prefork}"
    CONCURRENCY="${CELERY_CONCURRENCY:-2}"
    exec celery -A rb_exchange worker -l info --pool="$POOL" --concurrency="$CONCURRENCY"
    ;;
  beat)
    # Planification (DB scheduler)
    exec celery -A rb_exchange beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    exec "$@"
    ;;
esac
