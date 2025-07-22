# web_interface/views/admin_technique/dashboard.py

from django.shortcuts import render, redirect
# from django.db.models import Q # Plus nécessaire ici si la logique est dans shared.py
# from users.models import CustomUser # Plus nécessaire ici
from core.models.zone_monetaire import ZoneMonetaire
# MODIFICATION : Importer la fonction shared
from .shared import get_zones_with_status

def dashboard_view(request):
    if request.session.get("role") != "ADMIN_TECH":
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')

    # MODIFICATION : Appeler la fonction shared avec l'objet request
    # Et déstructurer les résultats : zones_data ET current_user_role
    zones_with_status_data, current_user_role = get_zones_with_status(request)

    # SUPPRESSION : Cette boucle est maintenant inutile car admin_zone_user est ajouté dans shared.py
    # for item in zones_with_status_data:
    #     item['admin_zone_user'] = CustomUser.objects.filter(
    #         zone=item['zone'],
    #         role='ADMIN_ZONE',
    #         is_active=True
    #     ).first()

    # Appliquer les filtres à la liste déjà enrichie
    filtered_zones_with_status = []
    for item in zones_with_status_data:
        # Appliquer le filtre de recherche (sur le nom de la zone)
        if search_query and search_query.lower() not in item['zone'].nom.lower():
            continue

        # Appliquer le filtre de statut
        if status_filter == 'active' and not item['zone'].is_active:
            continue
        if status_filter == 'inactive' and item['zone'].is_active:
            continue
        
        # Appliquer le filtre de zone par ID
        if zone_filter != 'all' and str(item['zone'].pk) != zone_filter:
             continue

        filtered_zones_with_status.append(item)

    context = {
        "zones_with_status": filtered_zones_with_status,
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "all_zones": ZoneMonetaire.objects.all(), # Pour la liste déroulante des filtres
        "current_user_role": current_user_role, # NOUVELLE LIGNE : Passer le rôle explicitement
    }

    if request.headers.get('HX-Request'):
        # MODIFICATION : Rendre le partial avec le contexte complet
        return render(request, "admin_technique/partials/_zones_table.html", context)
        
    # MODIFICATION : Rendre le template principal avec le contexte complet
    return render(request, "admin_technique/dashboard.html", context)