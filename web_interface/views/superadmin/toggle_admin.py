from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from users.models import CustomUser
from django.views.decorators.http import require_http_methods
from .shared import get_refreshed_dashboard_context_and_html
from logs.utils import log_action # Importation de log_action

@require_http_methods(["POST"])
def toggle_admin_view(request, pk):
    if request.session.get("role") != "SUPERADMIN":
        # MODIFICATION : Log pour accès non autorisé
        log_action(
            actor_id=request.session['user_id'],
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            details=f"Accès non autorisé pour basculer le statut d'un utilisateur par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
            level='warning'
        )
        return HttpResponse("Accès non autorisé.", status=403)

    user = get_object_or_404(CustomUser, pk=pk)

    if user.role == 'SUPERADMIN':
        log_details = ""
        error_message_ui = ""
        log_level = 'warning'
        
        if user.pk == request.session.get('user_id'): # Utiliser request.session.get('user_id') pour l'ID de l'utilisateur connecté
            log_details = f"Tentative de désactiver son propre compte SuperAdmin ({user.email}) par {request.session.get('email')}. Action bloquée."
            error_message_ui = "Impossible de désactiver votre propre compte SuperAdmin."
            log_action(
                actor_id=request.session['user_id'],
                action='SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                details=log_details,
                target_user_id=user.pk,
                level=log_level
            )
            response = HttpResponse(error_message_ui, status=400) # 400 pour un problème côté client (règle métier)
            response['HX-Trigger'] = '{"showError": "' + error_message_ui + '"}'
            return response
        else:
            log_details = f"Tentative de basculer le statut d'un autre SuperAdmin ({user.email}) par {request.session.get('email')}. Action bloquée."
            error_message_ui = "Action non autorisée sur un autre SuperAdmin."
            log_action(
                actor_id=request.session['user_id'],
                action='SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                details=log_details,
                target_user_id=user.pk,
                level=log_level
            )
            response = HttpResponse(error_message_ui, status=403) # 403 pour une permission
            response['HX-Trigger'] = '{"showError": "' + error_message_ui + '"}'
            return response

    # Si la modification de statut est autorisée
    old_status = "actif" if user.is_active else "inactif"
    user.is_active = not user.is_active
    user.save()
    new_status = "actif" if user.is_active else "inactif"

    # MODIFICATION : Message de log sémantique
    log_details = (
        f"L'utilisateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
        f"a basculé le statut de l'utilisateur {user.email} (ID: {user.pk}, Rôle: {user.get_role_display()}) "
        f"de '{old_status}' à '{new_status}'."
    )

    log_action(
        actor_id=request.session['user_id'],
        action='USER_STATUS_TOGGLED',
        details=log_details,
        target_user_id=user.pk,
        level='info'
    )

    context, html_content = get_refreshed_dashboard_context_and_html(request)
    response = HttpResponse(html_content)
    status_text = "activé" if user.is_active else "désactivé"
    response['HX-Trigger'] = f'{{"showInfo": "Utilisateur {user.email} {status_text} avec succès."}}'
    return response
