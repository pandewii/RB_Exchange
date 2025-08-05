from users.models import CustomUser
from core.models import ZoneMonetaire
from django.db.models import Q # Ensure Q is imported for complex queries

def get_refreshed_dashboard_context(request, search_query, status_filter, zone_filter_id, role_filter):
    """
    Récupère les données filtrées pour le tableau de bord SuperAdmin (admins et consommateurs).
    Cette fonction est conçue pour être appelée par HTMX pour rafraîchir uniquement les données.
    Elle ne retourne PAS de contenu HTML directement.
    """
    all_users_queryset = CustomUser.objects.all().select_related('zone').order_by('-date_joined')

    # Filtrage commun (texte de recherche)
    if search_query:
        all_users_queryset = all_users_queryset.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Filtrage par statut
    if status_filter == 'active':
        all_users_queryset = all_users_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        all_users_queryset = all_users_queryset.filter(is_active=False)

    # Filtrage par zone (pour ADMIN_ZONE et WS_USER)
    if zone_filter_id != 'all' and zone_filter_id:
        all_users_queryset = all_users_queryset.filter(zone__pk=zone_filter_id)

    # Séparation des administrateurs et des consommateurs
    admins_queryset = all_users_queryset.filter(
        role__in=['SUPERADMIN', 'ADMIN_TECH', 'ADMIN_ZONE']
    )
    consumers_queryset = all_users_queryset.filter(role='WS_USER')

    # Filtrage par rôle spécifique pour les admins (si demandé)
    if role_filter != 'all' and role_filter:
        if role_filter in ['ADMIN_TECH', 'ADMIN_ZONE']: # SUPERADMINs are always shown unless specifically filtered out
            admins_queryset = admins_queryset.filter(role=role_filter)
        # If SUPERADMIN filter is needed, it would be another condition
    
    # Exclude the current SUPERADMIN from the list of admins that can be modified/deleted by themselves.
    # This is a common UI/UX practice, although backend checks are the primary security.
    # We should exclude the current user from the list if they are a SUPERADMIN.
    if request.user.is_authenticated and request.user.role == 'SUPERADMIN':
        admins_queryset = admins_queryset.exclude(pk=request.user.pk)


    context = {
        'admins': admins_queryset,
        'consumers': consumers_queryset,
    }
    return context