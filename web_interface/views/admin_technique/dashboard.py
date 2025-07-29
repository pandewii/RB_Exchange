# web_interface/views/admin_technique/dashboard.py

from django.shortcuts import render, redirect
from core.models.zone_monetaire import ZoneMonetaire
from users.models import CustomUser
from logs.models import UINotification, LogEntry # Importer LogEntry
from .shared import get_zones_with_status
from django.http import HttpResponse
from django.db.models import Q # Importer Q pour les requêtes complexes

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

    # Récupération des notifications UI pour l'utilisateur connecté
    unread_notifications = []
    if request.user.is_authenticated:
        unread_notifications = UINotification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-timestamp')[:10]

    # AJOUT : Récupération des 5 derniers logs critiques/erreurs/warnings pertinents pour ADMIN_TECH
    # Ceci est pour une future section "Derniers Problèmes" sur le tableau de bord
    critical_errors_logs = []
    if request.user.is_authenticated:
        # Les actions que l'ADMIN_TECH doit voir rapidement
        relevant_actions_tech = [
            "SOURCE_CONFIGURATION_FAILED", "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR",
            "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START", "ZONE_DELETION_FAILED",
            "SCHEDULE_MANAGEMENT_FAILED", "UNAUTHORIZED_ACCESS_ATTEMPT", # etc.
        ]
        
        # Logs où l'ADMIN_TECH est l'acteur ou l'impersonateur, ou la cible (si pertinent)
        # OU les logs d'erreurs/warnings génériques du système
        critical_errors_logs = LogEntry.objects.filter(
            Q(level__in=['error', 'critical', 'warning']) &
            (
                Q(actor=request.user) |
                Q(impersonator=request.user) |
                Q(action__in=relevant_actions_tech) # Pour les logs système ou d'infrastructure
                # Si l'AdminTech est lié à une zone, on pourrait filtrer sur zone_id dans les détails ici
                # (nécessiterait de parser les détails ou d'ajouter zone_id directement au LogEntry model)
            )
        ).order_by('-timestamp')[:5]


    context = {
        "zones_with_status": filtered_zones_with_status,
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "all_zones": ZoneMonetaire.objects.all(),
        "current_user_role": current_user_role,
        "unread_notifications": unread_notifications,
        "critical_errors_logs": critical_errors_logs, # AJOUT: logs d'erreurs critiques
    }

    if request.headers.get('HX-Request'):
        # Lorsque c'est une requête HTMX (ex: filtre), on ne rend que la table des zones.
        # Il faudra s'assurer que les notifications et les logs d'erreurs sont rafraîchis via hx-swap-oob
        # dans le template principal ou en les incluant dans le partial si c'est pertinent.
        return render(request, "admin_technique/partials/_zones_table.html", context)
        
    return render(request, "admin_technique/dashboard.html", context)