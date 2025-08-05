# web_interface/views/superadmin/delete_admin.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from users.models import CustomUser
from core.models import ZoneMonetaire # ADDED: Import ZoneMonetaire
from .shared import get_refreshed_dashboard_context # CORRECTED IMPORT
from logs.utils import log_action 

class DeleteAdminView(View):
    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is a SUPERADMIN
        if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer un utilisateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_to_delete = get_object_or_404(CustomUser, pk=kwargs.get('pk'))
        context = {
            "user_to_delete": user_to_delete,
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "superadmin/partials/form_delete.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is a SUPERADMIN
        if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer un utilisateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None, 
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_id_to_delete = kwargs.get('pk')
        user_to_delete = get_object_or_404(CustomUser, pk=user_id_to_delete)

        log_zone_obj = user_to_delete.zone # Determine zone for logging

        log_level = 'info'
        action_type = 'USER_DELETED'
        error_message_ui = None
        log_details = ""

        if user_to_delete.role == 'SUPERADMIN':
            superadmins_count = CustomUser.objects.filter(role='SUPERADMIN').count()
            
            if superadmins_count == 1:
                log_details = f"Tentative de suppression du seul SuperAdmin ({user_to_delete.email}) par {request.user.email}. Action bloquée."
                error_message_ui = "Impossible de supprimer le seul SuperAdmin du système."
                action_type = 'SUPERADMIN_DELETION_FAILED'
                log_level = 'error'
            elif user_to_delete.pk == request.user.pk: # Compare with request.user.pk
                log_details = f"Tentative de suppression de son propre compte SuperAdmin ({user_to_delete.email}) par {request.user.email}. Action bloquée."
                error_message_ui = "Impossible de vous supprimer via cette interface."
                action_type = 'SUPERADMIN_DELETION_FAILED'
                log_level = 'warning'
            else:
                log_details = f"Tentative de suppression du SuperAdmin {user_to_delete.email} (ID: {user_to_delete.pk}) par {request.user.email} (ID: {request.user.pk}). Action bloquée."
                error_message_ui = "Action non autorisée sur un SuperAdmin."
                action_type = 'SUPERADMIN_DELETION_ATTEMPT_FAILED' 
                log_level = 'warning'

            log_action(
                actor_id=request.user.pk,
                action=action_type,
                details=log_details,
                target_user_id=user_to_delete.pk,
                level=log_level,
                zone_obj=log_zone_obj, 
                source_obj=None
            )

            context = {
                "user_to_delete": user_to_delete,
                "error_message": error_message_ui,
                "current_user_role": request.user.role, # Use request.user.role
            }
            html = render_to_string("superadmin/partials/form_delete.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message_ui}"}}'
            return response

        log_details = (
            f"L'utilisateur {request.user.email} (ID: {request.user.pk}, Rôle: {request.user.role}) "
            f"a supprimé l'utilisateur {user_to_delete.email} (ID: {user_to_delete.pk}, Rôle: {user_to_delete.get_role_display()})."
        )
        
        zone_of_deleted_user = user_to_delete.zone 
        user_pk_for_log = user_to_delete.pk 
        
        user_to_delete.delete() 

        # Correctly call the shared function to get context only, then render HTML
        dashboard_context = get_refreshed_dashboard_context(request, '', 'all', 'all', 'all') # Pass current filters or defaults
        dashboard_context.update({
            "all_zones": ZoneMonetaire.objects.all(), # Needed for filter dropdowns in dashboard.html partial
            "current_user_role": request.user.role,
        })
        html_content = render_to_string("superadmin/partials/_full_dashboard_content.html", dashboard_context, request=request)

        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur supprimé avec succès."}'
        return response