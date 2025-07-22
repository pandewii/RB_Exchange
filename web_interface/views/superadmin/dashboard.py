# web_interface/views/superadmin/dashboard.py

from django.shortcuts import render, redirect
# from django.db.models import Q # Plus nécessaire ici si la logique est dans shared.py
# from users.models import CustomUser # Plus nécessaire ici
# from core.models.zone_monetaire import ZoneMonetaire # Plus nécessaire ici

# MODIFICATION : Importer la fonction shared
from .shared import get_refreshed_dashboard_context_and_html

def dashboard_view(request):
    if request.session.get("role") != "SUPERADMIN":
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')
    role_filter = request.GET.get('role_filter', 'all')

    # MODIFICATION : Appeler la fonction shared avec tous les paramètres
    context, html_content = get_refreshed_dashboard_context_and_html(
        request, # Passer l'objet request
        search_query=search_query,
        status_filter=status_filter,
        zone_filter=zone_filter,
        role_filter=role_filter
    )
    
    # Le html_content n'est pas utilisé pour le rendu initial, mais le context l'est.
    # Pour le filtre de zone et de rôle dans le dashboard.html, vous avez besoin de toutes les zones
    # et des rôles d'administrateur disponibles. Cela est déjà dans le contexte retourné par get_refreshed...
    
    if request.headers.get('HX-Request'):
        # MODIFICATION : Retourner le HTML directement pour les requêtes HTMX
        return HttpResponse(html_content)

    # MODIFICATION : Retourner le rendu complet pour la première charge de la page
    return render(request, "superadmin/dashboard.html", context)