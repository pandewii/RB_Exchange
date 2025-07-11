from django.db import models
from .zone_monetaire import ZoneMonetaire
from .devise import Devise
from decimal import Decimal

class ExchangeRate(models.Model):
    """
    Table finale et propre contenant un taux de change validé pour une devise,
    une zone et une date de publication données.
    Stocke le taux brut de la source, son multiplicateur, et le taux normalisé.
    """
    devise = models.ForeignKey(Devise, on_delete=models.CASCADE, related_name='exchange_rates')
    zone = models.ForeignKey(ZoneMonetaire, on_delete=models.CASCADE, related_name='exchange_rates')
    
    date_publication = models.DateField(db_index=True)
    
    # CORRECTION: Taux tel qu'obtenu de la source (non normalisé)
    taux_source = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Taux brut de la source")
    
    # CORRECTION: Multiplicateur tel qu'obtenu de la source
    multiplicateur_source = models.IntegerField(verbose_name="Multiplicateur de la source", default=1)
    
    # CORRECTION: Taux normalisé (taux_source / multiplicateur_source)
    taux_normalise = models.DecimalField(max_digits=18, decimal_places=9, verbose_name="Taux normalisé (par unité)") # Augmenter decimal_places pour la précision de la normalisation

    date_creation_interne = models.DateTimeField(auto_now_add=True)
    
    is_latest = models.BooleanField(default=False, db_index=True, verbose_name="Est le taux le plus récent")

    class Meta:
        verbose_name = "Taux de Change Final"
        verbose_name_plural = "Taux de Change Finals"
        unique_together = ('devise', 'zone', 'date_publication')
        ordering = ['-date_publication', 'devise']

    def __str__(self):
        return (f"{self.devise.code} | {self.zone.nom} | {self.date_publication} | "
                f"Src: {self.taux_source} ({self.multiplicateur_source}) | Norm: {self.taux_normalise} "
                f"({'Latest' if self.is_latest else 'Old'})")