# api/views/raw_exchange_rates_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ExchangeRate
from users.permissions import IsWebServiceUserOnly
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


@extend_schema(
    parameters=[
        OpenApiParameter(name='currency', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='startDate', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='endDate', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='orderBy', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='direction', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY),
    ],
    responses={200: None}
)
class RawExchangeRatesView(APIView):
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request):
        currency_codes_str = request.query_params.get('currency')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        limit = request.query_params.get('limit')
        order_by = request.query_params.get('orderBy', 'date_publication')
        direction = request.query_params.get('direction', 'desc')

        user_zone = request.user.zone
        if not user_zone:
            return Response({"detail": "Votre compte WS_USER n'est pas associé à une zone monétaire."}, status=status.HTTP_403_FORBIDDEN)

        queryset = ExchangeRate.objects.filter(zone=user_zone)

        if currency_codes_str:
            currency_codes = [code.strip().upper() for code in currency_codes_str.split(',')]
            queryset = queryset.filter(devise__code__in=currency_codes)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(date_publication__gte=start_date)
            except ValueError:
                return Response({"error": "Date invalide pour 'startDate'."}, status=status.HTTP_400_BAD_REQUEST)
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    queryset = queryset.filter(date_publication__lte=end_date)
                except ValueError:
                    return Response({"error": "Date invalide pour 'endDate'."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            queryset = queryset.filter(is_latest=True)

        if order_by not in ['date_publication', 'devise__code', 'taux_source', 'multiplicateur_source']:
            return Response({"error": "Champ 'orderBy' invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if direction == 'desc':
            order_by = f'-{order_by}'
        elif direction != 'asc':
            return Response({"error": "Direction invalide."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = queryset.order_by(order_by)

        if limit:
            try:
                limit = int(limit)
                if limit <= 0:
                    raise ValueError
                queryset = queryset[:limit]
            except ValueError:
                return Response({"error": "Valeur 'limit' invalide."}, status=status.HTTP_400_BAD_REQUEST)

        results = [{
            "deviseId": rate.devise.code,
            "tauxSource": float(rate.taux_source),
            "multiplicateurSource": rate.multiplicateur_source,
            "datePublication": rate.date_publication.strftime("%Y-%m-%d"),
            "isLatest": rate.is_latest,
            "zoneId": rate.zone.pk,
            "zoneName": rate.zone.nom
        } for rate in queryset]

        return Response(results, status=status.HTTP_200_OK)
