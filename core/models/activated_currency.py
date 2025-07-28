from django.db import models
from .zone_monetaire import ZoneMonetaire
from .devise import Devise

class ActivatedCurrency(models.Model):
    """
    Définit si une devise officielle est activée pour une zone monétaire spécifique.
    C'est l'AdminZone qui contrôle le champ 'is_active'.
    """
    zone = models.ForeignKey(ZoneMonetaire, on_delete=models.CASCADE, related_name='activated_currencies')
    devise = models.ForeignKey(Devise, on_delete=models.CASCADE, related_name='activations')
    is_active = models.BooleanField(default=False, verbose_name="Statut d'activation")

    class Meta:
        verbose_name = "Devise Activée par Zone"
        verbose_name_plural = "Devises Activées par Zone"
        # Garantit qu'une devise ne peut être configurée qu'une seule fois par zone
        unique_together = ('zone', 'devise')

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.devise.code} dans {self.zone.nom} - Statut : {status}"
