from django.urls import path, include
from . import views # Importe les vues de l'application api

urlpatterns = [
    # URLs d'authentification pour les WS_USER (JWT)
    path('auth/', include('authentication.urls')),

    # URLs spécifiques à la consultation des taux de change
    # Ces vues seront définies dans api/views.py et utiliseront DRF
    path('rates/', views.ExchangeRateListView.as_view(), name='api_exchange_rate_list'),
    path('rates/latest/', views.LatestExchangeRateView.as_view(), name='api_latest_exchange_rates'),
    path('rates/historical/', views.HistoricalExchangeRateView.as_view(), name='api_historical_exchange_rates'),
    path('rates/latest-by-zone/', views.LatestRatesByZoneView.as_view(), name='api_latest_rates_by_zone'),
]