# web_interface/views/superadmin/delete_admin.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from users.models import CustomUser
from .shared import get_refreshed_dashboard_context_and_html
from logs.utils import log_action # Importation de log_action

class DeleteAdminView(View):
    def get(self, request, *args, **kwargs):
        if request.session.get("role") != "SUPERADMIN":
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_to_delete = get_object_or_404(CustomUser, pk=kwargs.get('pk'))
        context = {
            "user_to_delete": user_to_delete,
            "current_user_role": request.session.get('role'),
        }
        return render(request, "superadmin/partials/form_delete.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "SUPERADMIN":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer un utilisateur par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_id_to_delete = kwargs.get('pk')
        user_to_delete = get_object_or_404(CustomUser, pk=user_id_to_delete)

        log_level = 'info'
        action_type = 'USER_DELETED'
        error_message_ui = None
        log_details = ""

        if user_to_delete.role == 'SUPERADMIN':
            superadmins_count = CustomUser.objects.filter(role='SUPERADMIN').count()
            
            if superadmins_count == 1:
                log_details = f"Tentative de suppression du seul SuperAdmin ({user_to_delete.email}) par {request.session.get('email')}. Action bloquée."
                error_message_ui = "Impossible de supprimer le seul SuperAdmin du système."
                action_type = 'SUPERADMIN_DELETION_FAILED'
                log_level = 'error'
            elif str(user_to_delete.pk) == str(request.session.get('user_id')):
                log_details = f"Tentative de suppression de son propre compte SuperAdmin ({user_to_delete.email}) par {request.session.get('email')}. Action bloquée."
                error_message_ui = "Impossible de vous supprimer via cette interface."
                action_type = 'SUPERADMIN_DELETION_FAILED'
                log_level = 'warning'
            else:
                log_details = f"Tentative de suppression du SuperAdmin {user_to_delete.email} (ID: {user_to_delete.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}). Action bloquée."
                error_message_ui = "Action non autorisée sur un SuperAdmin."
                action_type = 'SUPERADMIN_DELETION_ATTEMPT_FAILED' # Nouveau type d'action pour la spécificité
                log_level = 'warning'

            log_action(
                actor_id=request.session['user_id'],
                action=action_type,
                details=log_details,
                target_user_id=user_to_delete.pk,
                level=log_level
            )

            context = {
                "user_to_delete": user_to_delete,
                "error_message": error_message_ui,
                "current_user_role": request.session.get('role'),
            }
            html = render_to_string("superadmin/partials/form_delete.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message_ui}"}}'
            return response

        # Si la suppression est autorisée
        log_details = f"L'utilisateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) a supprimé l'utilisateur {user_to_delete.email} (ID: {user_to_delete.pk}, Rôle: {user_to_delete.get_role_display()})."
        
        user_to_delete.delete()

        log_action(
            actor_id=request.session['user_id'],
            action='USER_DELETED',
            details=log_details,
            target_user_id=user_to_delete.pk,
            level='info'
        )

        context, html_content = get_refreshed_dashboard_context_and_html(request)
        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur supprimé avec succès."}'
        return response