# RB Exchange — Déploiement (Docker Compose)

## 0) Prérequis
- Serveur/VM avec Docker & Docker Compose
- Accès à une base PostgreSQL interne (host, db, user, password)
- Accès Internet sortant si les scrapers vont chercher des données externes

## 1) Déposer le pack
Décompresser l’archive dans un dossier (ex: /opt/rb_exchange/).

## 2) Configurer l'environnement
- Copier .env.example en .env
- Remplir:
  - SECRET_KEY (valeur forte)
  - ALLOWED_HOSTS (domaine ou IP interne)
  - Paramètres DB (DB_HOST/PORT/NAME/USER/PASSWORD)
  - CELERY_BROKER_URL / CELERY_RESULT_BACKEND
    - si Redis du compose: redis://redis:6379/0
    - si Redis corporate: URL fournie par l'IT

## 3) Premier démarrage
```bash
chmod +x entrypoint.sh
docker compose build
docker compose up -d
