# api/views/my_zone_currencies_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ActivatedCurrency, Devise, ExchangeRate
from users.permissions import IsWebServiceUserOnly
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


@extend_schema(
    parameters=[
        OpenApiParameter(
            name='date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Date spécifique pour récupérer les devises ayant un taux ce jour-là (YYYY-MM-DD)"
        )
    ],
    responses={200: None}
)
class MyZoneCurrenciesView(APIView):
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request):
        target_date_str = request.query_params.get('date')
        user_zone = request.user.zone

        if not user_zone:
            return Response({"detail": "Votre compte WS_USER n'est pas associé à une zone monétaire."}, status=status.HTTP_403_FORBIDDEN)

        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Format de date invalide. Utilisez YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            devise_ids = ExchangeRate.objects.filter(
                zone=user_zone,
                date_publication=target_date
            ).values_list('devise__pk', flat=True).distinct()

            active_devises = Devise.objects.filter(pk__in=devise_ids)

        else:
            active_devise_codes = ActivatedCurrency.objects.filter(
                zone=user_zone,
                is_active=True
            ).select_related('devise').values_list('devise__code', flat=True)

            devise_ids = ExchangeRate.objects.filter(
                zone=user_zone,
                devise__code__in=active_devise_codes,
                is_latest=True
            ).values_list('devise__pk', flat=True).distinct()

            active_devises = Devise.objects.filter(pk__in=devise_ids)

        results = [{"code": d.code, "name": d.nom} for d in active_devises]
        return Response(results, status=status.HTTP_200_OK)
