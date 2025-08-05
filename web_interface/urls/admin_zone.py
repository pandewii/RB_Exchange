# web_interface/urls/admin_zone.py

from django.urls import path
from web_interface.views.admin_zone import dashboard, toggle_activation # Importation de la classe

urlpatterns = [
    # CORRECTION: Utiliser .as_view() pour la classe AdminZoneDashboardView
    path('', dashboard.AdminZoneDashboardView.as_view(), name='admin_zone_dashboard'), # Corrected line
    # CORRECTION: Utiliser .as_view() pour la classe ToggleActivationView
    path('toggle-activation/<str:devise_code>/', toggle_activation.ToggleActivationView.as_view(), name='admin_zone_toggle_activation'),
]