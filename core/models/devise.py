from django.db import models

class Devise(models.Model):
    """
    Représente une devise officielle selon la norme ISO 4217.
    Exemple : 'USD' pour le Dollar Américain.
    """
    code = models.CharField(max_length=3, unique=True, primary_key=True, verbose_name="Code ISO")
    nom = models.CharField(max_length=100, verbose_name="Nom de la devise")

    class Meta:
        verbose_name = "Devise Officielle"
        verbose_name_plural = "Devises Officielles"
        ordering = ['code'] # Les devises seront triées par code alphabétique par défaut

    def __str__(self):
        return self.code
