from django.test import TestCase
from users.models import CustomUser
from core.models import ZoneMonetaire # Si CustomUser a une FK vers ZoneMonetaire

class CustomUserModelTest(TestCase):
    def test_create_user_with_email(self):
        user = CustomUser.objects.create_user(email='test@example.com', password='password123', role='ADMIN_TECH')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('password123'))
        self.assertEqual(user.role, 'ADMIN_TECH')

    def test_create_user_no_email_raises_error(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(email='', password='password123', role='ADMIN_TECH')

    def test_user_str_representation(self):
        user = CustomUser.objects.create_user(email='strtest@example.com', password='password', role='SUPERADMIN')
        self.assertEqual(str(user), "strtest@example.com (SuperAdmin)")

    def test_admin_zone_user_zone_assignment(self):
        zone = ZoneMonetaire.objects.create(nom="Test Zone")
        user = CustomUser.objects.create_user(email='adminzone@example.com', password='password', role='ADMIN_ZONE', zone=zone)
        self.assertEqual(user.zone, zone)
