# api/urls.py

from django.urls import path
from .views.exchange_rates_view import ExchangeRatesView
from .views.currency_convert_view import CurrencyConvertView
from .views.my_zone_currencies_view import MyZoneCurrenciesView
from .views.health_check_view import HealthCheckView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView # Pour l'authentification JWT

urlpatterns = [
    # Authentification JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 1. Accès aux Taux (Générique)
    path('exchange-rates/', ExchangeRatesView.as_view(), name='exchange_rates'),

    # 2. Conversion de Devises
    path('convert/', CurrencyConvertView.as_view(), name='convert_currency'),

    # 3. Liste des Devises Actives (Par Zone Implicite)
    path('my-zone-currencies/', MyZoneCurrenciesView.as_view(), name='my_zone_currencies'),

    # 4. Vérification de la Santé de l'API
    path('health/', HealthCheckView.as_view(), name='health_check'),
]
