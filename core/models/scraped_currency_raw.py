from django.db import models
from .source import Source
from decimal import Decimal

class ScrapedCurrencyRaw(models.Model):
    """
    Stocke une ligne de donnée brute telle que récupérée par un scraper,
    avant toute validation ou mapping. Simplifié pour un seul taux.
    """
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='raw_data')
    
    date_publication_brut = models.DateField(
        verbose_name="Date de publication brute",
        null=True, 
        blank=True
    )

    nom_devise_brut = models.CharField(max_length=100, verbose_name="Nom de la devise brute", blank=True)
    code_iso_brut = models.CharField(max_length=10, verbose_name="Code ISO brut", blank=True)
    
    # Correction: Un seul champ pour la valeur du taux brut
    valeur_brute = models.DecimalField(
        max_digits=18, 
        decimal_places=6, 
        verbose_name="Valeur brute du taux", 
        default=Decimal('0.0')
    )
    multiplicateur_brut = models.IntegerField(default=1)
    date_scraping = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Donnée Brute Scrapée"
        verbose_name_plural = "Données Brutes Scrapées"
        ordering = ['-date_publication_brut', '-date_scraping']
        unique_together = ('source', 'date_publication_brut', 'nom_devise_brut', 'code_iso_brut')


    def __str__(self):
        return f"{self.nom_devise_brut} ({self.date_publication_brut}) depuis {self.source.nom}"