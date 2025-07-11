import os
from celery import Celery

# Définir la variable d'environnement par défaut de Django pour les paramètres
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rb_exchange.settings')

# Créer une instance de l'application Celery
# Le nom de l'application est important et doit être unique
app = Celery('rb_exchange')

# Charger les paramètres de configuration Celery depuis les paramètres Django.
# Les clés de configuration Celery doivent être préfixées par 'CELERY_' dans settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découvrir et charger automatiquement les tâches des applications Django enregistrées.
# Celery va chercher les fichiers `tasks.py` dans toutes les applications listées dans INSTALLED_APPS.
app.autodiscover_tasks()

@app.task(bind=True, name="debug_task")
def debug_task(self):
    print(f'Request: {self.request!r}')