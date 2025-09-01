#!/usr/bin/env bash
set -e

# Optionnel : verbeux pour debug
# set -x

case "$1" in
  web)
    python manage.py migrate --noinput
    # collectstatic si tu utilises whitenoise/Nginx
    python manage.py collectstatic --noinput || true
    # Gunicorn avec timeouts & logs
    exec gunicorn rb_exchange.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers ${GUNICORN_WORKERS:-3} \
      --timeout ${GUNICORN_TIMEOUT:-120} \
      --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} \
      --access-logfile - \
      --error-logfile -
    ;;

  worker)
    POOL="${CELERY_POOL:-prefork}"
    CONCURRENCY="${CELERY_CONCURRENCY:-2}"
    # Quelques sécurités utiles en prod
    MAX_TASKS="${CELERY_MAX_TASKS_PER_CHILD:-100}"
    PREFETCH="${CELERY_PREFETCH_MULTIPLIER:-4}"
    exec celery -A rb_exchange worker -l info \
      --pool="$POOL" \
      --concurrency="$CONCURRENCY" \
      --max-tasks-per-child="$MAX_TASKS" \
      --prefetch-multiplier="$PREFETCH"
    ;;

  beat)
    # PID file pour éviter double Beat
    exec celery -A rb_exchange beat --loglevel=info \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler \
      --pidfile=/tmp/celerybeat.pid
    ;;

  *)
    exec "$@"
    ;;
esac
