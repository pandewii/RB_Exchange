# api/views/currency_convert_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ExchangeRate, Devise
from users.permissions import IsWebServiceUserOnly
from logs.utils import log_action
from decimal import Decimal, InvalidOperation
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from datetime import datetime
from django.db.models import Q # Add Q for advanced filtering

@extend_schema(
    parameters=[
        OpenApiParameter(
            name='amount',
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Montant à convertir (doit être > 0)"
        ),
        OpenApiParameter(
            name='fromCurrency',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False, # CHANGED: Not required anymore
            description="Code ISO de la devise source (ex: USD). Par défaut, c'est la devise de la zone du WS_USER."
        ),
        OpenApiParameter(
            name='toCurrency',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False, # CHANGED: Not required anymore
            description="Code ISO de la devise cible (ex: EUR). Par défaut, c'est la devise de la zone du WS_USER."
        ),
        OpenApiParameter(
            name='date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Date de conversion souhaitée (YYYY-MM-DD). Si omis, le dernier taux disponible sera utilisé."
        )
    ],
    responses={200: None}
)
class CurrencyConvertView(APIView):
    """
    API de conversion de devises pour utilisateurs WS_USER.
    Permet une conversion flexible en utilisant la devise de la zone par défaut.
    """
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request, *args, **kwargs):
        amount_str = request.query_params.get('amount')
        from_currency_code = request.query_params.get('fromCurrency', '').upper()
        to_currency_code = request.query_params.get('toCurrency', '').upper()
        date_str = request.query_params.get('date')

        if not amount_str:
            return Response(
                {"error": "Le paramètre 'amount' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_zone = request.user.zone
        if not user_zone:
            return Response({"error": "Votre compte WS_USER n'est pas associé à une zone monétaire."},
                            status=status.HTTP_403_FORBIDDEN)

        # Assigner la devise par défaut de la zone si l'un des champs est vide
        base_currency_code = user_zone.nom.upper()
        if not from_currency_code and not to_currency_code:
            return Response({"error": "Au moins un des champs 'fromCurrency' ou 'toCurrency' doit être spécifié."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not from_currency_code:
            from_currency_code = base_currency_code
        if not to_currency_code:
            to_currency_code = base_currency_code

        if from_currency_code == to_currency_code:
            converted_amount = Decimal(amount_str)
            exchange_rate_used = Decimal('1.0')
        else:
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    return Response({"error": "Le montant doit être un nombre positif."},
                                    status=status.HTTP_400_BAD_REQUEST)
            except InvalidOperation:
                return Response({"error": "Le montant 'amount' est invalide."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Fonction utilitaire pour récupérer le taux de manière intelligente
            def get_rate_value(currency_code, zone, date=None):
                if currency_code == base_currency_code:
                    return Decimal('1.0') # Taux implicite pour la devise de base

                if date:
                    rate_obj = ExchangeRate.objects.filter(
                        devise__code=currency_code,
                        zone=zone,
                        date_publication=date
                    ).first()
                else:
                    rate_obj = ExchangeRate.objects.filter(
                        devise__code=currency_code,
                        zone=zone,
                        is_latest=True
                    ).first()
                
                return rate_obj.taux_normalise if rate_obj else None

            from_rate = get_rate_value(from_currency_code, user_zone, date=date_str)
            to_rate = get_rate_value(to_currency_code, user_zone, date=date_str)

            if from_rate is None or to_rate is None:
                message = f"Taux introuvable pour {from_currency_code} ou {to_currency_code} dans votre zone."
                if date_str:
                    message += f" pour la date {date_str}."
                else:
                    message += " (dernier taux disponible)."
                return Response({"error": message + " Vérifiez les taux disponibles."}, status=status.HTTP_404_NOT_FOUND)

            exchange_rate_used = to_rate / from_rate
            converted_amount = amount * exchange_rate_used
        
        # Journalisation de l'opération de conversion
        log_action(
            actor_id=request.user.pk,
            action='API_CURRENCY_CONVERTED',
            details=f"Conversion via API: {amount_str} {from_currency_code} vers {to_currency_code} pour la zone '{user_zone.nom}'. Taux utilisé: {float(exchange_rate_used.quantize(Decimal('0.000000001')))}.",
            level='info',
            zone_obj=user_zone,
            currency_code=from_currency_code,
            target_user_id=request.user.pk
        )

        return Response({
            "fromCurrency": from_currency_code,
            "toCurrency": to_currency_code,
            "amount": float(Decimal(amount_str)),
            "convertedAmount": float(converted_amount.quantize(Decimal('0.01'))),
            "exchangeRateUsed": float(exchange_rate_used.quantize(Decimal('0.000000001'))),
            "source": date_str if date_str else "Dernier taux disponible (is_latest)"
        }, status=status.HTTP_200_OK)