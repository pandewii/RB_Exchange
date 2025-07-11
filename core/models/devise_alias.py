from django.db import models
from .devise import Devise

class DeviseAlias(models.Model):
    """
    C'est notre dictionnaire de traduction centralisé.
    Il fait le lien entre un nom de devise brute (unique)
    et une devise officielle.
    L'alias est toujours stocké en MAJUSCULES pour ignorer la casse.
    """
    alias = models.CharField(max_length=100, unique=True, primary_key=True, verbose_name="Nom brut / Alias")
    devise_officielle = models.ForeignKey(Devise, on_delete=models.CASCADE, related_name='aliases')

    class Meta:
        verbose_name = "Alias de Devise"
        verbose_name_plural = "Alias de Devises"

    def __str__(self):
        return f'"{self.alias}" -> {self.devise_officielle.code}'

    def save(self, *args, **kwargs):
        # CORRECTION: Normaliser l'alias en majuscules avant de sauvegarder
        self.alias = self.alias.upper()
        super().save(*args, **kwargs)