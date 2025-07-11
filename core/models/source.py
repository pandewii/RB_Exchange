# core/models/source.py

from django.db import models
from .zone_monetaire import ZoneMonetaire
from django_celery_beat.models import PeriodicTask

class Source(models.Model):
    zone = models.OneToOneField(
        ZoneMonetaire,
        on_delete=models.CASCADE,
        related_name='source',
        primary_key=True
    )
    nom = models.CharField(max_length=200, verbose_name="Nom de la source")
    url_source = models.URLField(max_length=255, verbose_name="URL de la source de données")
    scraper_filename = models.CharField(max_length=100, verbose_name="Nom du fichier scraper")
    date_creation = models.DateTimeField(auto_now_add=True)

    # On lie notre Source à une tâche planifiée.
    # Si on supprime la Source, la tâche planifiée associée sera aussi supprimée.
    periodic_task = models.OneToOneField(
        PeriodicTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="La tâche planifiée Celery Beat pour ce scraper."
    )

    class Meta:
        verbose_name = "Source de Données"
        verbose_name_plural = "Sources de Données"

    def __str__(self):
        return self.nom