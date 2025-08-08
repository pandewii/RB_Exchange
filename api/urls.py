from django.urls import path
from .views.exchange_rates_view import ExchangeRatesView
from .views.currency_convert_view import CurrencyConvertView
from .views.my_zone_currencies_view import MyZoneCurrenciesView
from .views.raw_exchange_rates_view import RawExchangeRatesView 
 


urlpatterns = [
    

    # 1. Accès aux Taux (Générique)
    path('exchange-rates/', ExchangeRatesView.as_view(), name='exchange_rates'),

    # 2. Conversion de Devises
    path('convert/', CurrencyConvertView.as_view(), name='convert_currency'),

    # 3. Liste des Devises Actives (Par Zone Implicite)
    path('my-zone-currencies/', MyZoneCurrenciesView.as_view(), name='my_zone_currencies'),

    # 4. Accès aux Taux Non Normalisés (Raw Exchange Rates)
    path('raw-exchange-rates/', RawExchangeRatesView.as_view(), name='raw_exchange_rates'),

]