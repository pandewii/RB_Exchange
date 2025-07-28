# core/serializers/zone_monetaire.py

from rest_framework import serializers
from core.models import ZoneMonetaire

class ZoneMonetaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZoneMonetaire
        fields = '__all__' # On expose tous les champs du modèle ZoneMonetaire
