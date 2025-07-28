# web_interface/views/superadmin/shared.py

from django.template.loader import render_to_string
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from logs.models import UINotification
from django.db.models import Q 

def get_refreshed_dashboard_context_and_html(request, search_query="", status_filter="all", zone_filter="all", role_filter="all"):
    admin_roles = ['ADMIN_TECH', 'ADMIN_ZONE']
    consumer_roles = ['WS_USER']
    
    admins_queryset = CustomUser.objects.filter(role__in=admin_roles)
    consumers_queryset = consumers_queryset = CustomUser.objects.filter(role__in=consumer_roles)

    if search_query:
        search_filter_q = (
            Q(email__icontains=search_query) | 
            Q(username__icontains=search_query)
        )
        admins_queryset = admins_queryset.filter(search_filter_q)
        consumers_queryset = consumers_queryset.filter(search_filter_q)

    if status_filter == 'active':
        admins_queryset = admins_queryset.filter(is_active=True)
        consumers_queryset = consumers_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        admins_queryset = admins_queryset.filter(is_active=False)
        consumers_queryset = consumers_queryset.filter(is_active=False)
        
    if zone_filter != 'all' and zone_filter.isdigit():
        admins_queryset = admins_queryset.filter(zone_id=int(zone_filter))
        consumers_queryset = consumers_queryset.filter(zone_id=int(zone_filter))

    if role_filter != 'all':
        admins_queryset = admins_queryset.filter(role=role_filter)
        
    admins = admins_queryset.order_by("id")
    consumers = consumers_queryset.order_by("id")

    context = {
        "admins": admins,
        "consumers": consumers,
        "zones": ZoneMonetaire.objects.all(),
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "selected_role": role_filter,
        "current_user_role": request.session.get('role'),
    }
    
    unread_notifications = []
    if request.user.is_authenticated:
        unread_notifications = UINotification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-timestamp')[:10]
    context['unread_notifications'] = unread_notifications # Les notifications sont dans le contexte

    html_main_content = render_to_string("superadmin/partials/dashboard_content.html", context, request=request)
    
    # RETOURNE 2 VALEURS SEULEMENT (context et html_main_content)
    return context, html_main_content