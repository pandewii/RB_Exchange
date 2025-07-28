from django.db import models

class ZoneMonetaire(models.Model):
    """
    Représente une zone monétaire (ex: Zone TND, Zone DZD).
    Chaque zone aura sa propre source de données et ses propres configurations.
    """
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom de la zone")
    is_active = models.BooleanField(default=True, verbose_name="Statut Actif")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zone Monétaire"
        verbose_name_plural = "Zones Monétaires"
        ordering = ['nom'] # Les zones seront triées par nom par défaut

    def __str__(self):
        return self.nom
