# api/tests.py

from django.test import TestCase
from django.urls import reverse
from core.models.zone_monetaire import ZoneMonetaire
from core.models.devise import Devise
from core.models.exchange_rate import ExchangeRate
from core.models.activated_currency import ActivatedCurrency
from datetime import date
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient # Import APIClient

CustomUser = get_user_model()

class BaseAPITestCase(TestCase):
    """
    Base class for API test cases to handle user creation and authentication.
    """
    def setUp(self):
        self.zone_tnd = ZoneMonetaire.objects.create(nom="TND")
        self.zone_dzd = ZoneMonetaire.objects.create(nom="DZD")

        # Create a WS_USER for API access
        self.ws_user = CustomUser.objects.create_user(
            email="wsuser@example.com",
            password="testpassword",
            role="WS_USER",
            zone=self.zone_tnd # Assign a zone to the WS_USER
        )
        
        # Use APIClient for testing DRF views
        self.client = APIClient() 
        
        # Get JWT token for the WS_USER
        self.refresh_token = RefreshToken.for_user(self.ws_user)
        self.access_token = str(self.refresh_token.access_token)
        
        # Set the Authorization header for all subsequent requests by this client
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')


class ExchangeRatesAPITestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp() # Call the parent setUp to create user and zone
        self.devise_usd = Devise.objects.create(code="USD", nom="Dollar US")
        self.devise_eur = Devise.objects.create(code="EUR", nom="Euro")

        # Create ExchangeRate objects with correct field names
        ExchangeRate.objects.create(
            devise=self.devise_usd,
            zone=self.zone_tnd,
            taux_source=2.9056,
            multiplicateur_source=1,
            taux_normalise=2.9056,
            date_publication=date(2025, 7, 24),
            is_latest=True
        )
        ExchangeRate.objects.create(
            devise=self.devise_eur,
            zone=self.zone_tnd,
            taux_source=3.3595,
            multiplicateur_source=1,
            taux_normalise=3.3595,
            date_publication=date(2025, 7, 24),
            is_latest=True
        )
        # Add a historical rate for testing date filtering
        ExchangeRate.objects.create(
            devise=self.devise_usd,
            zone=self.zone_tnd,
            taux_source=2.9000,
            multiplicateur_source=1,
            taux_normalise=2.9000,
            date_publication=date(2025, 7, 20),
            is_latest=False # This is an old rate
        )


    def test_exchange_rates_latest(self):
        # Test fetching latest rates for the user's zone
        response = self.client.get(reverse('exchange_rates'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2) # Expecting USD and EUR for TND zone
        self.assertTrue(any(item['deviseId'] == 'USD' for item in data))
        self.assertTrue(any(item['deviseId'] == 'EUR' for item in data))
        self.assertTrue(all(item['isLatest'] == True for item in data))


    def test_exchange_rates_with_currency_and_date(self):
        # Test fetching historical rates for a specific currency and date range
        url = reverse('exchange_rates') + "?currency=USD&startDate=2025-07-20&endDate=2025-07-24"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2) # Expecting two USD rates for the date range
        self.assertTrue(any(item['datePublication'] == '2025-07-20' for item in data))
        self.assertTrue(any(item['datePublication'] == '2025-07-24' for item in data))
        self.assertTrue(all(item['deviseId'] == 'USD' for item in data))


class CurrencyConversionAPITestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp() # Call the parent setUp
        self.devise_dzd = Devise.objects.create(code="DZD", nom="Dinar Algérien")
        self.devise_eur = Devise.objects.create(code="EUR", nom="Euro")
        self.devise_usd = Devise.objects.create(code="USD", nom="Dollar US")


        # Rates for TND zone (assuming TND is the base for these rates)
        ExchangeRate.objects.create(
            devise=self.devise_dzd,
            zone=self.zone_tnd, # WS_USER is in TND zone
            taux_source=0.2249,
            multiplicateur_source=10,
            taux_normalise=0.02249, # 1 DZD = 0.02249 TND (example)
            date_publication=date(2025, 7, 24),
            is_latest=True
        )

        ExchangeRate.objects.create(
            devise=self.devise_eur,
            zone=self.zone_tnd, # WS_USER is in TND zone
            taux_source=3.3595,
            multiplicateur_source=1,
            taux_normalise=3.3595, # 1 EUR = 3.3595 TND (example)
            date_publication=date(2025, 7, 24),
            is_latest=True
        )
        ExchangeRate.objects.create(
            devise=self.devise_usd,
            zone=self.zone_tnd, # WS_USER is in TND zone
            taux_source=2.9056,
            multiplicateur_source=1,
            taux_normalise=2.9056, # 1 USD = 2.9056 TND (example)
            date_publication=date(2025, 7, 24),
            is_latest=True
        )


    def test_conversion_api(self):
        # Test DZD to EUR conversion
        # 320 DZD to EUR via TND: (320 * 0.02249 TND/DZD) / 3.3595 TND/EUR
        # Expected: (320 * 0.02249) / 3.3595 = 7.1968 / 3.3595 = 2.14234...
        url = reverse('convert_currency') + "?fromCurrency=DZD&toCurrency=EUR&amount=320"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("convertedAmount", data)
        self.assertAlmostEqual(data['convertedAmount'], 2.14, places=2) # Check with a reasonable precision

    def test_conversion_same_currency(self):
        # Test conversion from a currency to itself
        url = reverse('convert_currency') + "?fromCurrency=USD&toCurrency=USD&amount=100"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['convertedAmount'], 100.0)
        self.assertEqual(data['exchangeRateUsed'], 1.0)

    def test_conversion_missing_rates(self):
        # Create a new zone and currencies without rates to test missing rate scenario
        zone_new = ZoneMonetaire.objects.create(nom="XYZ")
        devise_x = Devise.objects.create(code="XXX", nom="Devise X")
        devise_y = Devise.objects.create(code="YYY", nom="Devise Y")

        # Temporarily change user's zone for this specific test
        self.ws_user.zone = zone_new
        self.ws_user.save()
        # Re-authenticate the client with the updated user's zone
        self.client = APIClient()
        self.refresh_token = RefreshToken.for_user(self.ws_user)
        self.access_token = str(self.refresh_token.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        url = reverse('convert_currency') + "?fromCurrency=XXX&toCurrency=YYY&amount=100"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Taux introuvable", response.json()['error'])


class MyZoneCurrenciesAPITestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp() # Call the parent setUp
        self.devise_usd = Devise.objects.create(code="USD", nom="Dollar US")
        self.devise_eur = Devise.objects.create(code="EUR", nom="Euro")
        self.devise_gbp = Devise.objects.create(code="GBP", nom="Livre Sterling")

        # Activate USD and EUR for TND zone
        ActivatedCurrency.objects.create(devise=self.devise_usd, zone=self.zone_tnd, is_active=True)
        ActivatedCurrency.objects.create(devise=self.devise_eur, zone=self.zone_tnd, is_active=True)
        # GBP is active but no latest rate
        ActivatedCurrency.objects.create(devise=self.devise_gbp, zone=self.zone_tnd, is_active=True)


        # Add latest rates for USD and EUR in TND zone
        ExchangeRate.objects.create(
            devise=self.devise_usd,
            zone=self.zone_tnd,
            taux_source=2.9056,
            multiplicateur_source=1,
            taux_normalise=2.9056,
            date_publication=date(2025, 7, 24),
            is_latest=True
        )
        ExchangeRate.objects.create(
            devise=self.devise_eur,
            zone=self.zone_tnd,
            taux_source=3.3595,
            multiplicateur_source=1,
            taux_normalise=3.3595,
            date_publication=date(2025, 7, 24),
            is_latest=True
        )
        # Add an old rate for GBP, so it shouldn't appear in default list
        ExchangeRate.objects.create(
            devise=self.devise_gbp,
            zone=self.zone_tnd,
            taux_source=3.8000,
            multiplicateur_source=1,
            taux_normalise=3.8000,
            date_publication=date(2025, 7, 20),
            is_latest=False
        )


    def test_my_zone_currencies_latest(self):
        # Test listing active currencies with latest rates for the user's zone
        url = reverse('my_zone_currencies')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Expecting USD and EUR, but not GBP because it doesn't have a latest rate
        self.assertEqual(len(data), 2)
        self.assertTrue(any(item['code'] == 'USD' for item in data))
        self.assertTrue(any(item['code'] == 'EUR' for item in data))
        self.assertFalse(any(item['code'] == 'GBP' for item in data))

    def test_my_zone_currencies_with_date(self):
        # Test listing currencies that had a rate on a specific date
        url = reverse('my_zone_currencies') + "?date=2025-07-20"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Expecting only GBP for this date (as USD and EUR latest are 24th)
        self.assertEqual(len(data), 1)
        self.assertTrue(any(item['code'] == 'GBP' for item in data))
        self.assertFalse(any(item['code'] == 'USD' for item in data))
        self.assertFalse(any(item['code'] == 'EUR' for item in data))

