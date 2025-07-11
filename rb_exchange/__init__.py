# S'assurer que l'application Celery est importée lorsque Django démarre.
# Cela permet à shared_task de fonctionner correctement.
from .celery import app as celery_app

__all__ = ('celery_app',)