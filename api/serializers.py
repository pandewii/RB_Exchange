from rest_framework import serializers
from core.models import ExchangeRate, Devise, ZoneMonetaire

class DeviseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Devise
        fields = ['code', 'nom']

class ZoneMonetaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZoneMonetaire
        fields = ['id', 'nom', 'is_active']

class ExchangeRateSerializer(serializers.ModelSerializer):
    devise = DeviseSerializer() # Inclure les détails de la devise
    zone = ZoneMonetaireSerializer() # Inclure les détails de la zone

    class Meta:
        model = ExchangeRate
        # Correction: Remplacer 'taux' par les nouveaux champs
        fields = ['devise', 'zone', 'date_publication', 'taux_source', 'multiplicateur_source', 'taux_normalise', 'is_latest']

class LatestRatesByZoneSerializer(serializers.Serializer):
    # Ce sérialiseur est pour la sortie agrégée (par exemple, les derniers taux pour une zone)
    zone_id = serializers.IntegerField(write_only=True, required=False) # Pour filtrer si nécessaire
    zone_nom = serializers.CharField(read_only=True)
    rates = ExchangeRateSerializer(many=True, read_only=True)

