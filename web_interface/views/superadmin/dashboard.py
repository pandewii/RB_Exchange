from django.shortcuts import render, redirect
from django.db.models import Q
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire

def dashboard_view(request):
    if request.session.get("role") != "SUPERADMIN":
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')
    role_filter = request.GET.get('role_filter', 'all') # NOUVEAU

    # Définir les rôles pour chaque table
    admin_roles = ['ADMIN_TECH', 'ADMIN_ZONE']
    consumer_roles = ['WS_USER']
    
    # Préparer les requêtes de base
    admins_queryset = CustomUser.objects.filter(role__in=admin_roles)
    consumers_queryset = CustomUser.objects.filter(role__in=consumer_roles)

    # Appliquer le filtre de recherche
    if search_query:
        search_filter_q = (
            Q(email__icontains=search_query) | 
            Q(username__icontains=search_query)
        )
        admins_queryset = admins_queryset.filter(search_filter_q)
        consumers_queryset = consumers_queryset.filter(search_filter_q)

    # Appliquer le filtre de statut
    if status_filter == 'active':
        admins_queryset = admins_queryset.filter(is_active=True)
        consumers_queryset = consumers_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        admins_queryset = admins_queryset.filter(is_active=False)
        consumers_queryset = consumers_queryset.filter(is_active=False)
        
    # Appliquer le filtre de zone
    if zone_filter != 'all' and zone_filter.isdigit():
        admins_queryset = admins_queryset.filter(zone_id=int(zone_filter))
        consumers_queryset = consumers_queryset.filter(zone_id=int(zone_filter))

    # DÉBUT DE L'AJOUT : Appliquer le filtre de rôle
    if role_filter != 'all':
        # Ce filtre ne s'applique QU'AU queryset des administrateurs
        admins_queryset = admins_queryset.filter(role=role_filter)
    # FIN DE L'AJOUT
        
    # Ordonner les résultats finaux
    admins = admins_queryset.order_by("id")
    consumers = consumers_queryset.order_by("id")

    # Préparer le contexte pour le template
    context = {
        "admins": admins,
        "consumers": consumers,
        "search_query": search_query,
        "status": status_filter,
        "zones": ZoneMonetaire.objects.all(),
        "selected_zone_id": zone_filter,
        "selected_role": role_filter, # NOUVEAU
    }

    if request.headers.get('HX-Request'):
        return render(request, "superadmin/partials/dashboard_content.html", context)

    return render(request, "superadmin/dashboard.html", context)