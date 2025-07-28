# web_interface/views/superadmin/dashboard.py

from django.shortcuts import render, redirect
from django.http import HttpResponse 
from django.template.loader import render_to_string 
from core.models.zone_monetaire import ZoneMonetaire
from users.models import CustomUser
from logs.models import UINotification
from .shared import get_refreshed_dashboard_context_and_html

def dashboard_view(request):
    user_role = request.session.get("role")
    if user_role != "SUPERADMIN":
        return redirect("login")

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')
    role_filter = request.GET.get('role_filter', 'all')

    # MODIFICATION : S'attendre à 2 valeurs seulement
    context, html_dynamic_content = get_refreshed_dashboard_context_and_html(
        request,
        search_query=search_query,
        status_filter=status_filter,
        zone_filter=zone_filter,
        role_filter=role_filter
    )
    
    # Les notifications non lues sont déjà dans le contexte ici (ajoutées par shared.py)
    # context['unread_notifications'] = ... (Cette ligne est gérée dans shared.py)

    if request.headers.get('HX-Request'):
        # NE PAS FAIRE D'OOB SWAP POUR LES FILTRES ICI
        return HttpResponse(html_dynamic_content)

    return render(request, "superadmin/dashboard.html", context)
