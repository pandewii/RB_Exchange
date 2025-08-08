# api/views/exchange_rates_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ExchangeRate, Devise
from users.permissions import IsWebServiceUserOnly
from datetime import datetime
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


@extend_schema(
    parameters=[
        OpenApiParameter(name='currency', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="Codes devises séparés par virgules (ex: USD,EUR)"),
        OpenApiParameter(name='startDate', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, description="Date début (YYYY-MM-DD)"),
        OpenApiParameter(name='endDate', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, description="Date fin (YYYY-MM-DD)"),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description="Nombre maximum de résultats"),
        OpenApiParameter(name='orderBy', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="Champ de tri : date_publication, devise__code, taux_normalise"),
        OpenApiParameter(name='direction', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="asc ou desc"),
    ],
    responses={200: None}
)
class ExchangeRatesView(APIView):
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request, *args, **kwargs):
        currency_codes_str = request.query_params.get('currency')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        limit = request.query_params.get('limit')
        order_by = request.query_params.get('orderBy', 'date_publication')
        direction = request.query_params.get('direction', 'desc')

        queryset = ExchangeRate.objects.all()

        if request.user.zone:
            queryset = queryset.filter(zone=request.user.zone)
        else:
            return Response({"detail": "Votre compte WS_USER n'est pas associé à une zone monétaire."}, status=status.HTTP_403_FORBIDDEN)

        if currency_codes_str:
            currency_codes = [code.strip().upper() for code in currency_codes_str.split(',')]
            queryset = queryset.filter(devise__code__in=currency_codes)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(date_publication__gte=start_date)
            except ValueError:
                return Response({"error": "Format invalide pour 'startDate'. Utilisez YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    queryset = queryset.filter(date_publication__lte=end_date)
                except ValueError:
                    return Response({"error": "Format invalide pour 'endDate'. Utilisez YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            queryset = queryset.filter(is_latest=True)

        if order_by not in ['date_publication', 'devise__code', 'taux_normalise']:
            return Response({"error": "Champ 'orderBy' invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if direction == 'desc':
            order_by = f'-{order_by}'
        elif direction == 'asc':
            pass
        else:
            return Response({"error": "Direction invalide. Utilisez 'asc' ou 'desc'."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = queryset.order_by(order_by)

        if limit:
            try:
                limit = int(limit)
                if limit <= 0:
                    raise ValueError
                queryset = queryset[:limit]
            except ValueError:
                return Response({"error": "Paramètre 'limit' invalide."}, status=status.HTTP_400_BAD_REQUEST)

        results = [{
            "deviseId": rate.devise.code,
            "tauxNormalise": float(rate.taux_normalise),
            "datePublication": rate.date_publication.strftime("%Y-%m-%d"),
            "isLatest": rate.is_latest,
            "zoneId": rate.zone.pk,
            "zoneName": rate.zone.nom
        } for rate in queryset]

        return Response(results, status=status.HTTP_200_OK)
