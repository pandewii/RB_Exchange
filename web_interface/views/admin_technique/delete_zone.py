# web_interface/views/admin_technique/delete_zone.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser 
from .shared import get_zones_with_status
from logs.utils import log_action 

class DeleteZoneView(View):

    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour afficher le formulaire de suppression de zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,    
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)
        context = {
            "zone": zone,
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/partials/form_delete_zone.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer la zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,    
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        # Start impersonation logic setup for logging
        actor_id_for_log = request.user.pk
        impersonator_id_for_log = None
        current_active_user_obj = request.user # This is already the current user after auth middleware

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Fetch actual user objects for logging details, if necessary
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log) if actor_id_for_log else None
        impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log) if impersonator_id_for_log else None
        # End impersonation logic setup

        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk) # Get the zone object early

        if zone.users.exists():
            error_message = f"Impossible de supprimer la zone '{zone.nom}' car elle est associée à des utilisateurs. Veuillez d'abord les désassocier."
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='ZONE_DELETION_FAILED',
                details=f"Échec de la suppression de la zone '{zone.nom}' (ID: {zone.pk}) par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}) car elle est associée à des utilisateurs.",
                target_user_id=None, 
                level='warning',
                zone_obj=zone, 
                source_obj=None
            )
            response = HttpResponse(status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        # --- Logging of successful deletion BEFORE actual deletion ---
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk: 
                 details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
        else: 
            details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

        log_details = (
            f"{details_prefix} a supprimé la zone monétaire '{zone.nom}' (ID: {zone.pk})."
        )
        
        # Call log_action with zone_obj set to None because the zone is about to be deleted.
        # The relevant information (zone.nom, zone.pk) is already in log_details string.
        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='ZONE_DELETED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=None, # Pass None for zone_obj as it will be deleted
            source_obj=None
        )

        # Now perform the actual deletion
        zone.delete() 

        zones_data, current_user_role = get_zones_with_status(request)
        
        html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role,
            },
            request=request
        )
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Zone supprimée avec succès."}'
        return response