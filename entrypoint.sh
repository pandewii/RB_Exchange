#!/usr/bin/env bash
set -e

MODE="${1:-web}"

# ===== Wait-for-Postgres =====
: "${DB_HOST:?DB_HOST non défini}"
: "${DB_PORT:?DB_PORT non défini}"

echo "⏳ Waiting for Postgres at $DB_HOST:$DB_PORT ..."
until nc -z -v -w30 "$DB_HOST" "$DB_PORT"; do
  echo "  Postgres not ready yet..."
  sleep 2
done
echo "✅ Postgres is up."

# ===== Migrations =====
python manage.py migrate --noinput

# ===== Collect static (optionnel) =====
if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

# ===== Run mode =====
case "$MODE" in
  web)
    echo "🚀 Starting Django dev server on 0.0.0.0:8000"
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    echo "⚙️  Starting Celery worker (app=${CELERY_APP:-config})"
    exec celery -A "${CELERY_APP:-config}" worker -l info
    ;;
  beat)
    echo "⏰ Starting Celery beat (app=${CELERY_APP:-config})"
    exec celery -A "${CELERY_APP:-config}" beat -l info
    ;;
  *)
    echo "Unknown mode '$MODE'. Use: web | worker | beat"
    exit 1
    ;;
esac
