# web_interface/views/admin_technique/dashboard.py

from django.shortcuts import render, redirect
from core.models.zone_monetaire import ZoneMonetaire
from users.models import CustomUser
from logs.models import UINotification
from .shared import get_zones_with_status
from django.http import HttpResponse

def dashboard_view(request):
    user_role = request.session.get("role")
    if user_role != "ADMIN_TECH":
        # Redirection vers la page de login si le rôle n'est pas ADMIN_TECH ou non authentifié.
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')

    # Appeler la fonction shared avec l'objet request
    zones_with_status_data, current_user_role = get_zones_with_status(request)

    # Appliquer les filtres à la liste déjà enrichie
    filtered_zones_with_status = []
    for item in zones_with_status_data:
        if search_query and search_query.lower() not in item['zone'].nom.lower():
            continue
        if status_filter == 'active' and not item['zone'].is_active:
            continue
        if status_filter == 'inactive' and item['zone'].is_active:
            continue
        if zone_filter != 'all' and str(item['zone'].pk) != zone_filter:
             continue

        filtered_zones_with_status.append(item)

    # MODIFICATION : Vérifier si l'utilisateur est authentifié avant de récupérer les notifications
    unread_notifications = []
    if request.user.is_authenticated: # AJOUT DE LA CONDITION
        unread_notifications = UINotification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-timestamp')[:10]

    context = {
        "zones_with_status": filtered_zones_with_status,
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "all_zones": ZoneMonetaire.objects.all(),
        "current_user_role": current_user_role,
        "unread_notifications": unread_notifications,
    }

    if request.headers.get('HX-Request'):
        return render(request, "admin_technique/partials/_zones_table.html", context)
        
    return render(request, "admin_technique/dashboard.html", context)
