from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import ExchangeRate, Devise, ZoneMonetaire, ActivatedCurrency
from .serializers import ExchangeRateSerializer, LatestRatesByZoneSerializer # Importe les sérialiseurs créés

class ExchangeRateListView(generics.ListAPIView):
    """
    Récupère une liste de taux de change.
    Permet de filtrer par devise (code ISO), zone et/ou date de publication.
    Exemples:
    /api/rates/?currency=USD
    /api/rates/?zone=1
    /api/rates/?currency=EUR&zone=2&date=2023-01-01
    """
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ExchangeRate.objects.all().select_related('devise', 'zone')
        
        currency_code = self.request.query_params.get('currency', None)
        zone_id = self.request.query_params.get('zone', None)
        date_str = self.request.query_params.get('date', None)

        if currency_code:
            queryset = queryset.filter(devise__code__iexact=currency_code)
        if zone_id:
            try:
                queryset = queryset.filter(zone__id=int(zone_id))
            except ValueError:
                pass # Ignorer si zone_id n'est pas un entier valide
        if date_str:
            try:
                queryset = queryset.filter(date_publication=date_str)
            except ValueError:
                pass # Ignorer si date_str n'est pas un format de date valide

        # Assurer que seuls les taux des devises activées sont retournés pour la zone
        # Ceci est une mesure de sécurité et de conformité avec la logique métier
        # Pour le WS_USER, il doit voir seulement ce qui est activé pour sa zone
        if self.request.user.role == 'WS_USER':
            user_zone = self.request.user.zone
            if user_zone:
                activated_devise_codes = ActivatedCurrency.objects.filter(zone=user_zone, is_active=True).values_list('devise__code', flat=True)
                queryset = queryset.filter(devise__code__in=activated_devise_codes, zone=user_zone)
            else:
                # Si un WS_USER n'a pas de zone, il ne peut voir aucun taux
                queryset = ExchangeRate.objects.none()

        return queryset.order_by('-date_publication', 'devise__code')

class LatestExchangeRateView(APIView):
    """
    Récupère le dernier taux de change pour une devise et/ou une zone.
    Exemples:
    /api/rates/latest/?currency=USD&zone=1
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        currency_code = request.query_params.get('currency', None)
        zone_id = request.query_params.get('zone', None)

        if not currency_code and not zone_id:
            return Response({"error": "Veuillez spécifier au moins un 'currency' ou 'zone'."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = ExchangeRate.objects.all().select_related('devise', 'zone')

        if currency_code:
            queryset = queryset.filter(devise__code__iexact=currency_code)
        if zone_id:
            try:
                queryset = queryset.filter(zone__id=int(zone_id))
            except ValueError:
                return Response({"error": "L'ID de zone doit être un entier valide."}, status=status.HTTP_400_BAD_REQUEST)

        # Appliquer la même logique de permission basée sur la zone de l'utilisateur
        if request.user.role == 'WS_USER':
            user_zone = request.user.zone
            if user_zone:
                activated_devise_codes = ActivatedCurrency.objects.filter(zone=user_zone, is_active=True).values_list('devise__code', flat=True)
                queryset = queryset.filter(devise__code__in=activated_devise_codes, zone=user_zone)
            else:
                queryset = ExchangeRate.objects.none() # Aucun taux si pas de zone assignée

        if not queryset.exists():
            return Response({"message": "Aucun taux trouvé pour les critères spécifiés."}, status=status.HTTP_404_NOT_FOUND)
        
        # Trouver la date de publication la plus récente dans le queryset filtré
        latest_date = queryset.aggregate(Max('date_publication'))['date_publication__max']
        if not latest_date:
            return Response({"message": "Aucun taux avec une date de publication valide trouvé."}, status=status.HTTP_404_NOT_FOUND)

        # Récupérer tous les taux pour cette dernière date (pour gérer plusieurs devises si le filtre est large)
        latest_rates = queryset.filter(date_publication=latest_date).order_by('devise__code')
        
        serializer = ExchangeRateSerializer(latest_rates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HistoricalExchangeRateView(generics.ListAPIView):
    """
    Récupère les taux de change historiques pour une devise et une zone sur une période donnée.
    Requiert 'currency' et 'zone'. Peut prendre 'start_date' et 'end_date'.
    Exemples:
    /api/rates/historical/?currency=USD&zone=1&start_date=2023-01-01&end_date=2023-01-31
    """
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        currency_code = self.request.query_params.get('currency', None)
        zone_id = self.request.query_params.get('zone', None)
        start_date_str = self.request.query_params.get('start_date', None)
        end_date_str = self.request.query_params.get('end_date', None)

        if not currency_code or not zone_id:
            raise serializers.ValidationError({"error": "Les paramètres 'currency' et 'zone' sont obligatoires."})

        queryset = ExchangeRate.objects.filter(
            devise__code__iexact=currency_code,
            zone__id=zone_id
        ).select_related('devise', 'zone')

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date_publication__gte=start_date)
            except ValueError:
                raise serializers.ValidationError({"start_date": "Format de date invalide. Utilisez YYYY-MM-DD."})
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date_publication__lte=end_date)
            except ValueError:
                raise serializers.ValidationError({"end_date": "Format de date invalide. Utilisez YYYY-MM-DD."})
        
        # Appliquer la même logique de permission basée sur la zone de l'utilisateur
        if self.request.user.role == 'WS_USER':
            user_zone = self.request.user.zone
            if user_zone:
                activated_devise_codes = ActivatedCurrency.objects.filter(zone=user_zone, is_active=True).values_list('devise__code', flat=True)
                if currency_code not in activated_devise_codes: # Vérifier si la devise demandée est activée
                    queryset = ExchangeRate.objects.none()
                elif int(zone_id) != user_zone.id: # Vérifier si la zone demandée est celle de l'utilisateur
                    queryset = ExchangeRate.objects.none()
            else:
                queryset = ExchangeRate.objects.none() # Aucun taux si pas de zone assignée

        return queryset.order_by('date_publication')


class LatestRatesByZoneView(APIView):
    """
    Récupère les derniers taux de change pour toutes les devises activées d'une zone spécifique.
    Le WS_USER ne peut voir que les taux de sa propre zone.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Pour les WS_USER, la zone est déterminée par leur profil
        if request.user.role == 'WS_USER':
            user_zone = request.user.zone
            if not user_zone:
                return Response({"error": "Vous n'êtes pas assigné à une zone pour récupérer les taux."}, status=status.HTTP_400_BAD_REQUEST)
            target_zone = user_zone
        else:
            # Pour d'autres rôles admin accédant à l'API, ils pourraient spécifier la zone
            # Si l'API est strictement pour WS_USER, cette partie pourrait être retirée.
            zone_id = request.query_params.get('zone_id')
            if not zone_id:
                return Response({"error": "Le paramètre 'zone_id' est requis."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                target_zone = get_object_or_404(ZoneMonetaire, id=zone_id)
            except ValueError:
                return Response({"error": "L'ID de zone doit être un entier valide."}, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer les codes des devises activées pour cette zone
        activated_devises_codes = ActivatedCurrency.objects.filter(zone=target_zone, is_active=True).values_list('devise__code', flat=True)

        if not activated_devises_codes.exists():
            return Response({"message": f"Aucune devise activée pour la zone {target_zone.nom}."}, status=status.HTTP_404_NOT_NOT_FOUND) # Correction: HTTP_404_NOT_FOUND

        latest_rates_data = []
        for devise_code in activated_devises_codes:
            # Trouver la date de publication la plus récente pour cette devise dans cette zone
            latest_date_for_devise = ExchangeRate.objects.filter(
                devise__code=devise_code,
                zone=target_zone
            ).aggregate(Max('date_publication'))['date_publication__max']

            if latest_date_for_devise:
                # Récupérer le taux pour cette dernière date
                latest_rate = ExchangeRate.objects.filter(
                    devise__code=devise_code,
                    zone=target_zone,
                    date_publication=latest_date_for_devise
                ).select_related('devise', 'zone').first()
                
                if latest_rate:
                    latest_rates_data.append(latest_rate)
        
        if not latest_rates_data:
            return Response({"message": f"Aucun taux disponible pour les devises activées de la zone {target_zone.nom}."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExchangeRateSerializer(latest_rates_data, many=True)
        return Response({
            "zone_nom": target_zone.nom,
            "rates": serializer.data
        }, status=status.HTTP_200_OK)

