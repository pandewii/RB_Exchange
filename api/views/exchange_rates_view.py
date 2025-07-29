# api/views/exchange_rates_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ExchangeRate, Devise
from users.permissions import IsWebServiceUserOnly # Importation de la permission mise à jour
from logs.utils import log_action # Assurez-vous que logs.utils est correctement importé
from datetime import datetime, date
from django.db.models import Q

class ExchangeRatesView(APIView):
    """
    Endpoint API pour récupérer les taux de change.
    Permet le filtrage par devise, plage de dates et pagination.
    Accessible uniquement par les utilisateurs WS_USER.
    """
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request, *args, **kwargs):
        # Puisque la permission IsWebServiceUserOnly est appliquée,
        # seul un WS_USER peut atteindre ce point.
        # Le logging pour SuperAdmin n'est donc pas nécessaire ici pour l'accès.

        currency_codes_str = request.query_params.get('currency')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        limit = request.query_params.get('limit')
        order_by = request.query_params.get('orderBy', 'date_publication')
        direction = request.query_params.get('direction', 'desc')

        queryset = ExchangeRate.objects.all()

        # Filtrer par la zone de l'utilisateur WS_USER
        # Un WS_USER est toujours associé à une zone, comme défini dans le modèle CustomUser.
        if request.user.zone:
            queryset = queryset.filter(zone=request.user.zone)
        else:
            # Si, pour une raison quelconque, un WS_USER n'a pas de zone, refuser l'accès.
            # Cela ne devrait normalement pas arriver si le modèle CustomUser est bien configuré.
            return Response({"detail": "Votre compte WS_USER n'est pas associé à une zone monétaire."}, status=status.HTTP_403_FORBIDDEN)


        # Filtrer par les codes de devise
        if currency_codes_str:
            currency_codes = [code.strip().upper() for code in currency_codes_str.split(',')]
            queryset = queryset.filter(devise__code__in=currency_codes)

        # Gérer le filtrage par date (mode historique)
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(date_publication__gte=start_date)
            except ValueError:
                return Response({"error": "Format de date invalide pour 'startDate'. Utilisez YYYY-MM-DD."},
                                status=status.HTTP_400_BAD_REQUEST)

            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    queryset = queryset.filter(date_publication__lte=end_date)
                except ValueError:
                    return Response({"error": "Format de date invalide pour 'endDate'. Utilisez YYYY-MM-DD."},
                                    status=status.HTTP_400_BAD_REQUEST)
            
            # En mode historique, is_latest n'est pas utilisé pour le filtrage
        else:
            # Par défaut, obtenir les taux les plus récents si aucune plage de dates n'est spécifiée
            queryset = queryset.filter(is_latest=True)


        # Tri
        if order_by not in ['date_publication', 'devise__code', 'taux_normalise']:
            return Response({"error": "Le champ 'orderBy' n'est pas valide. Les options sont 'date_publication', 'devise__code', 'taux_normalise'."},
                            status=status.HTTP_400_BAD_REQUEST)

        if direction == 'desc':
            order_by = f'-{order_by}'
        elif direction == 'asc':
            order_by = f'{order_by}'
        else:
            return Response({"error": "La direction 'direction' n'est pas valide. Utilisez 'asc' ou 'desc'."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        queryset = queryset.order_by(order_by)

        # Limiter les résultats
        if limit:
            try:
                limit = int(limit)
                if limit <= 0:
                    raise ValueError
                queryset = queryset[:limit]
            except ValueError:
                return Response({"error": "La limite 'limit' doit être un entier positif."},
                                status=status.HTTP_400_BAD_REQUEST)

        results = []
        for rate in queryset:
            results.append({
                "deviseId": rate.devise.code,
                "tauxNormalise": float(rate.taux_normalise), # Convertir Decimal en float pour JSON
                "datePublication": rate.date_publication.strftime("%Y-%m-%d"),
                "isLatest": rate.is_latest,
                "zoneId": rate.zone.pk,
                "zoneName": rate.zone.nom
            })

        return Response(results, status=status.HTTP_200_OK)
