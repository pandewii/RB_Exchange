# web_interface/views/superadmin/shared.py

from django.template.loader import render_to_string
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from django.db.models import Q # Importation nécessaire

# MODIFICATION : La fonction doit accepter l'objet 'request'
def get_refreshed_dashboard_context_and_html(request, search_query="", status_filter="all", zone_filter="all", role_filter="all"):
    """
    Fonction utilitaire qui centralise la logique de récupération des données
    du tableau de bord SuperAdmin et le rendu du template partiel.
    Elle prend maintenant les paramètres de filtre pour pouvoir rafraîchir le tableau filtré.
    """
    admin_roles = ['ADMIN_TECH', 'ADMIN_ZONE']
    consumer_roles = ['WS_USER']
    
    # Préparer les querysets en fonction des rôles
    admins_queryset = CustomUser.objects.filter(role__in=admin_roles)
    consumers_queryset = CustomUser.objects.filter(role__in=consumer_roles)

    # Appliquer le filtre de recherche (commun aux deux)
    if search_query:
        search_filter_q = (
            Q(email__icontains=search_query) | 
            Q(username__icontains=search_query)
        )
        admins_queryset = admins_queryset.filter(search_filter_q)
        consumers_queryset = consumers_queryset.filter(search_filter_q)

    # Appliquer le filtre de statut (commun aux deux)
    if status_filter == 'active':
        admins_queryset = admins_queryset.filter(is_active=True)
        consumers_queryset = consumers_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        admins_queryset = admins_queryset.filter(is_active=False)
        consumers_queryset = consumers_queryset.filter(is_active=False)
        
    # Appliquer le filtre de zone (commun aux deux)
    if zone_filter != 'all' and zone_filter.isdigit():
        admins_queryset = admins_queryset.filter(zone_id=int(zone_filter))
        consumers_queryset = consumers_queryset.filter(zone_id=int(zone_filter))

    # Appliquer le filtre de rôle (spécifique aux admins)
    if role_filter != 'all':
        admins_queryset = admins_queryset.filter(role=role_filter)
        
    # Ordonner les résultats finaux
    admins = admins_queryset.order_by("id")
    consumers = consumers_queryset.order_by("id")

    context = {
        "admins": admins,
        "consumers": consumers,
        "zones": ZoneMonetaire.objects.all(), # Pour la liste déroulante des filtres
        # Réinjecter les paramètres de filtre pour maintenir l'état de l'UI
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "selected_role": role_filter,
        "current_user_role": request.session.get('role'), # NOUVELLE LIGNE : Passer le rôle explicitement
    }
    
    # La fonction retourne maintenant le contexte ET le HTML pour plus de flexibilité.
    html = render_to_string("superadmin/partials/dashboard_content.html", context, request=request)
    return context, html # MODIFICATION : Retourne le contexte et le HTML