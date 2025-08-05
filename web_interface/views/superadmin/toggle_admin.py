from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from users.models import CustomUser
from django.views.decorators.http import require_http_methods
from .shared import get_refreshed_dashboard_context # CORRECTED IMPORT
from logs.utils import log_action
from django.template.loader import render_to_string # ADDED for rendering HTML
from core.models import ZoneMonetaire # Needed for fetching all zones for dashboard context

@require_http_methods(["POST"])
def toggle_admin_view(request, pk):
    # Access control: Ensure user is authenticated and is a SuperAdmin
    if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
        log_action(
            actor_id=request.user.pk if request.user.is_authenticated else None,
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            details=f"Accès non autorisé pour basculer le statut d'un utilisateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
            level='warning'
        )
        return HttpResponse("Accès non autorisé.", status=403)

    user = get_object_or_404(CustomUser, pk=pk)
    
    log_zone_obj = user.zone # Determine zone for logging

    if user.role == 'SUPERADMIN':
        log_details = ""
        error_message_ui = ""
        log_level = 'warning'
        
        if user.pk == request.user.pk: # Compare with request.user.pk
            log_details = f"Tentative de désactiver son propre compte SuperAdmin ({user.email}) par {request.user.email}. Action bloquée."
            error_message_ui = "Impossible de désactiver votre propre compte SuperAdmin."
            log_action(
                actor_id=request.user.pk,
                action='SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                details=log_details,
                target_user_id=user.pk,
                level=log_level,
                zone_obj=log_zone_obj, 
                source_obj=None
            )
            response = HttpResponse(error_message_ui, status=400)
            response['HX-Trigger'] = '{"showError": "' + error_message_ui + '"}'
            return response
        else:
            log_details = f"Tentative de basculer le statut d'un autre SuperAdmin ({user.email}) par {request.user.email}. Action bloquée."
            error_message_ui = "Action non autorisée sur un autre SuperAdmin."
            log_action(
                actor_id=request.user.pk,
                action='SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                details=log_details,
                target_user_id=user.pk,
                level=log_level,
                zone_obj=log_zone_obj, 
                source_obj=None
            )
            response = HttpResponse(error_message_ui, status=403) 
            response['HX-Trigger'] = '{"showError": "' + error_message_ui + '"}'
            return response

    old_status = "actif" if user.is_active else "inactif"
    user.is_active = not user.is_active
    user.save()
    new_status = "actif" if user.is_active else "inactif"

    log_details = (
        f"L'utilisateur {request.user.email} (ID: {request.user.pk}, Rôle: {request.user.role}) "
        f"a basculé le statut de l'utilisateur {user.email} (ID: {user.pk}, Rôle: {user.get_role_display()}) "
        f"de '{old_status}' à '{new_status}'."
    )

    log_action(
        actor_id=request.user.pk,
        action='USER_STATUS_TOGGLED',
        details=log_details,
        target_user_id=user.pk,
        level='info',
        zone_obj=log_zone_obj, 
        source_obj=None
    )

    # Correctly call the shared function to get context only, then render HTML
    dashboard_context = get_refreshed_dashboard_context(request, '', 'all', 'all', 'all') # Pass current filters or defaults
    dashboard_context.update({
        "all_zones": ZoneMonetaire.objects.all(), # Needed for filter dropdowns in dashboard.html partial
        "current_user_role": request.user.role,
    })
    html_content = render_to_string("superadmin/partials/_full_dashboard_content.html", dashboard_context, request=request)

    response = HttpResponse(html_content)
    status_text = "activé" if user.is_active else "désactivé"
    response['HX-Trigger'] = f'{{"showInfo": "Utilisateur {user.email} {status_text} avec succès."}}'
    return response