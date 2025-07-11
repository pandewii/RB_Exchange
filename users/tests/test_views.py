from rest_framework.test import APITestCase
from rest_framework import status
from users.models import CustomUser
from core.models import ZoneMonetaire

class UserAPIViewTests(APITestCase):
    def setUp(self):
        self.superadmin = CustomUser.objects.create_superuser('super@test.com', 'password')
        self.admin_tech = CustomUser.objects.create_user('tech@test.com', 'password', role='ADMIN_TECH')
        self.zone = ZoneMonetaire.objects.create(nom="Zone A")
        self.admin_zone = CustomUser.objects.create_user('zone@test.com', 'password', role='ADMIN_ZONE', zone=self.zone)
        self.client.force_authenticate(user=self.superadmin) # Authentifier le client pour les tests

    def test_superadmin_can_toggle_admin_status(self):
        response = self.client.patch(f'/api/users/toggle/{self.admin_tech.pk}/') # Assurez-vous que cette URL existe et pointe vers votre vue
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_tech.refresh_from_db()
        self.assertFalse(self.admin_tech.is_active) # Vérifier que le statut a changé
        self.assertIn('désactivé', response.data['message'])

    def test_superadmin_cannot_toggle_superadmin_status(self):
        response = self.client.patch(f'/api/users/toggle/{self.superadmin.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Impossible de modifier le statut d’un SuperAdmin.', response.data['error'])