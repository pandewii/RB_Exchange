# api/views/currency_convert_view.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import ExchangeRate, Devise
from users.permissions import IsWebServiceUserOnly
from logs.utils import log_action
from decimal import Decimal, InvalidOperation


class CurrencyConvertView(APIView):
    """
    API de conversion de devises pour utilisateurs WS_USER.
    Utilise toujours les derniers taux disponibles (is_latest=True).
    """
    permission_classes = [IsWebServiceUserOnly]

    def get(self, request, *args, **kwargs):
        # Paramètres de la requête
        amount_str = request.query_params.get('amount')
        from_currency_code = request.query_params.get('fromCurrency', '').upper()
        to_currency_code = request.query_params.get('toCurrency', '').upper()

        # Vérification des paramètres requis
        if not all([amount_str, from_currency_code, to_currency_code]):
            return Response(
                {"error": "Les paramètres 'amount', 'fromCurrency' et 'toCurrency' sont requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation du montant
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                return Response({"error": "Le montant doit être un nombre positif."},
                                status=status.HTTP_400_BAD_REQUEST)
        except InvalidOperation:
            return Response({"error": "Le montant 'amount' est invalide."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Récupération des devises
        try:
            from_devise = Devise.objects.get(code=from_currency_code)
            to_devise = Devise.objects.get(code=to_currency_code)
        except Devise.DoesNotExist:
            return Response({"error": "Une des devises spécifiées n'existe pas."},
                            status=status.HTTP_404_NOT_FOUND)

        # Zone monétaire de l'utilisateur (WS_USER)
        user_zone = request.user.zone
        if not user_zone:
            return Response({"error": "Votre compte WS_USER n'est pas associé à une zone monétaire."},
                            status=status.HTTP_403_FORBIDDEN)

        # Fonction pour récupérer le dernier taux de change (is_latest=True)
        def get_latest_rate(devise, zone):
            return ExchangeRate.objects.filter(
                devise=devise,
                zone=zone,
                is_latest=True
            ).order_by('-date_creation_interne').first()

        from_rate_obj = get_latest_rate(from_devise, user_zone)
        to_rate_obj = get_latest_rate(to_devise, user_zone)

        # Vérifier que les deux taux sont disponibles
        if not from_rate_obj or not to_rate_obj:
            return Response({
                "error": f"Taux introuvable pour {from_currency_code} ou {to_currency_code} dans votre zone. Vérifiez les taux disponibles."
            }, status=status.HTTP_404_NOT_FOUND)

        # Conversion
        if from_currency_code == to_currency_code:
            converted_amount = amount
            exchange_rate_used = Decimal('1.0')
        else:
            exchange_rate_used = from_rate_obj.taux_normalise / to_rate_obj.taux_normalise
            converted_amount = amount * exchange_rate_used

        # Réponse
        return Response({
            "fromCurrency": from_currency_code,
            "toCurrency": to_currency_code,
            "amount": float(amount),
            "convertedAmount": float(converted_amount.quantize(Decimal('0.01'))),
            "exchangeRateUsed": float(exchange_rate_used.quantize(Decimal('0.000000001'))),
            "source": "Dernier taux disponible (is_latest)"
        }, status=status.HTTP_200_OK)
