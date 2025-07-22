# web_interface/views/admin_technique/dashboard.py

from django.shortcuts import render, redirect
from django.db.models import Q
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from .shared import get_zones_with_status # Assurez-vous d'importer cette fonction

def dashboard_view(request):
    if request.session.get("role") != "ADMIN_TECH":
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')

    # Utiliser la fonction partagée pour obtenir les zones avec leur statut
    zones_with_status_data = get_zones_with_status()

    # AJOUT : Récupérer l'AdminZone pour chaque zone
    for item in zones_with_status_data:
        # CORRECTION : Accéder à 'zone' comme une clé de dictionnaire
        item['admin_zone_user'] = CustomUser.objects.filter(
            zone=item['zone'], # Modifié : item.zone -> item['zone']
            role='ADMIN_ZONE',
            is_active=True
        ).first()

    # Appliquer les filtres à la liste déjà enrichie
    filtered_zones_with_status = []
    for item in zones_with_status_data:
        # CORRECTION : Accéder à 'zone' comme une clé de dictionnaire
        # Appliquer le filtre de recherche (sur le nom de la zone)
        if search_query and search_query.lower() not in item['zone'].nom.lower(): # Modifié : item.zone.nom -> item['zone'].nom
            continue

        # Appliquer le filtre de statut
        if status_filter == 'active' and not item['zone'].is_active: # Modifié : item.zone.is_active -> item['zone'].is_active
            continue
        if status_filter == 'inactive' and item['zone'].is_active: # Modifié : item.zone.is_active -> item['zone'].is_active
            continue
        
        # Appliquer le filtre de zone par ID
        if zone_filter != 'all' and str(item['zone'].pk) != zone_filter: # Modifié : item.zone.pk -> item['zone'].pk
             continue

        filtered_zones_with_status.append(item)

    context = {
        "zones_with_status": filtered_zones_with_status,
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "all_zones": ZoneMonetaire.objects.all(),
    }

    if request.headers.get('HX-Request'):
        return render(request, "admin_technique/partials/_zones_table.html", context)
        
    return render(request, "admin_technique/dashboard.html", context)