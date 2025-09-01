FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Deps système (psycopg2, build…)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc libpq-dev curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie l’ensemble du projet (plus robuste si requirements.txt est absent/ignoré)
COPY . /app

# Installe les deps si requirements.txt existe
RUN if [ -f req.txt ]; then pip install -r req.txt; fi

# Rendre l'entrypoint exécutable (LF côté git déjà géré par .gitattributes)
RUN chmod +x /app/entrypoint.sh

# === Sécurité: utilisateur non-root ===
RUN addgroup --system app && adduser --system --ingroup app app \
  && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
