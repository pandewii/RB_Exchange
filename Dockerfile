# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps pour psycopg2 / gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY req.txt /app/req.txt
RUN pip install --upgrade pip && pip install -r /app/req.txt

# Code
COPY . /app

# User non-root (bonnes pratiques)
RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 8000

# Par défaut : démarrer le web (overridable par docker-compose)
CMD ["bash", "-lc", "./entrypoint.sh web"]
