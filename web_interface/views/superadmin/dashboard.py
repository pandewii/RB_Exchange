# web_interface/views/superadmin/dashboard.py

from django.shortcuts import render, redirect
from core.models.zone_monetaire import ZoneMonetaire
from users.models import CustomUser
from logs.models import UINotification
from .shared import get_refreshed_dashboard_context_and_html
from django.http import HttpResponse

def dashboard_view(request):
    user_role = request.session.get("role")
    if user_role != "SUPERADMIN":
        # Redirection vers la page de login si le rôle n'est pas SUPERADMIN ou non authentifié.
        # Cela devrait gérer le cas AnonymousUser pour la vue principale.
        return redirect("login")

    # Récupérer tous les paramètres de filtre depuis la requête GET
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')
    role_filter = request.GET.get('role_filter', 'all')

    # Appeler la fonction shared avec tous les paramètres
    context, html_content = get_refreshed_dashboard_context_and_html(
        request,
        search_query=search_query,
        status_filter=status_filter,
        zone_filter=zone_filter,
        role_filter=role_filter
    )
    
    # MODIFICATION : Vérifier si l'utilisateur est authentifié avant de récupérer les notifications
    unread_notifications = []
    if request.user.is_authenticated: # AJOUT DE LA CONDITION
        unread_notifications = UINotification.objects.filter(
            user=request.user, 
            is_read=False
        ).order_by('-timestamp')[:10]

    context['unread_notifications'] = unread_notifications
    
    if request.headers.get('HX-Request'):
        return HttpResponse(html_content)

    return render(request, "superadmin/dashboard.html", context)