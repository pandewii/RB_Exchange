# api/views/my_zone_currencies_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ActivatedCurrency, Devise, ExchangeRate
from users.permissions import IsWebServiceUserOnly # Importation de la permission mise à jour
from logs.utils import log_action # Assurez-vous que logs.utils est correctement importé
from datetime import datetime, date
from django.db.models import Q

class MyZoneCurrenciesView(APIView):
    """
    Endpoint API pour lister les devises actives pour la zone du système appelant.
    Accessible uniquement par les utilisateurs WS_USER.
    """
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request, *args, **kwargs):
        # Puisque la permission IsWebServiceUserOnly est appliquée,
        # seul un WS_USER peut atteindre ce point.
        # Le logging pour SuperAdmin n'est donc pas nécessaire ici.

        target_date_str = request.query_params.get('date')

        # La zone de l'utilisateur WS_USER est implicite
        user_zone = request.user.zone
        if not user_zone:
            return Response({"detail": "Votre compte WS_USER n'est pas associé à une zone monétaire."}, status=status.HTTP_403_FORBIDDEN)


        currencies = []
        if target_date_str:
            # Lister les devises pour lesquelles un taux existait à la date spécifiée
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Format de date invalide. Utilisez YYYY-MM-DD."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Obtenir les devises distinctes qui ont un taux de change pour la zone et la date données
            devise_ids_with_rates = ExchangeRate.objects.filter(
                zone=user_zone,
                date_publication=target_date
            ).values_list('devise__pk', flat=True).distinct()

            # Filtrer les objets Devise en fonction de ces IDs
            active_devises = Devise.objects.filter(pk__in=devise_ids_with_rates)

        else:
            # Par défaut : Lister les devises actives avec les taux "latest" pour la zone implicite
            # Obtenir tous les objets ActivatedCurrency qui sont actifs pour la zone de l'utilisateur
            active_currencies_query = ActivatedCurrency.objects.filter(
                zone=user_zone,
                is_active=True
            ).select_related('devise')

            # Obtenir les codes de ces devises actives
            active_devise_codes = [ac.devise.code for ac in active_currencies_query]

            # Filtrer ExchangeRate pour s'assurer que ces devises actives ont également un taux 'latest'
            # Cela garantit que nous ne renvoyons que les devises qui sont à la fois actives ET qui ont des taux actuels.
            devise_ids_with_latest_rates = ExchangeRate.objects.filter(
                zone=user_zone,
                devise__code__in=active_devise_codes,
                is_latest=True
            ).values_list('devise__pk', flat=True).distinct()

            active_devises = Devise.objects.filter(pk__in=devise_ids_with_latest_rates)


        for devise in active_devises:
            currencies.append({
                "code": devise.code,
                "name": devise.nom
            })

        return Response(currencies, status=status.HTTP_200_OK)
