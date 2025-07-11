# web_interface/views/superadmin/shared.py

from django.template.loader import render_to_string
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire

def get_refreshed_dashboard_context_and_html():
    """
    Fonction utilitaire qui centralise la logique de récupération des données
    du tableau de bord SuperAdmin et le rendu du template partiel.
    """
    admin_roles = ['ADMIN_TECH', 'ADMIN_ZONE']
    consumer_roles = ['WS_USER']
    
    context = {
        "admins": CustomUser.objects.filter(role__in=admin_roles).order_by("id"),
        "consumers": CustomUser.objects.filter(role__in=consumer_roles).order_by("id"),
        "zones": ZoneMonetaire.objects.all(),
        # On réinitialise les filtres lors d'une action
        "status": "all",
        "search_query": "",
        "selected_zone_id": "all",
        "selected_role": "all",
    }
    
    html = render_to_string("superadmin/partials/dashboard_content.html", context)
    return html