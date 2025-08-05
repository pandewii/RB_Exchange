# web_interface/views/admin_technique/toggle_zone.py

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from core.models import ZoneMonetaire, Source
from users.models import CustomUser
from .shared import get_zones_with_status
from logs.utils import log_action
from django_celery_beat.models import PeriodicTask

class ToggleZoneView(View):
    def post(self, request, pk):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer le statut de la zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
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

        zone = get_object_or_404(ZoneMonetaire, pk=pk)

        old_status = "active" if zone.is_active else "inactive"
        zone.is_active = not zone.is_active
        zone.save()
        new_status = "active" if zone.is_active else "inactif"

        # NEW LOGIC: Synchronize associated PeriodicTask.enabled with zone.is_active
        if hasattr(zone, 'source') and zone.source and zone.source.periodic_task:
            periodic_task = zone.source.periodic_task
            
            if periodic_task.enabled != zone.is_active:
                periodic_task.enabled = zone.is_active
                periodic_task.save(update_fields=["enabled"])
                
                task_status_log = "activée" if zone.is_active else "désactivée"
                log_action(
                    actor_id=actor_id_for_log,
                    impersonator_id=impersonator_id_for_log,
                    action='SCHEDULE_STATUS_SYNCHRONIZED_WITH_ZONE',
                    details=f"Planification '{periodic_task.name}' (ID: {periodic_task.pk}) pour la source '{zone.source.nom}' a été {task_status_log} suite au basculement de statut de la zone '{zone.nom}'.",
                    level='info',
                    zone_obj=zone,
                    source_obj=zone.source
                )

        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                 details_prefix += f" et exécuté par {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"
        else:
            details_prefix = f"L'administrateur {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"


        log_details = (
            f"{details_prefix} a basculé le statut de la zone '{zone.nom}' (ID: {zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )
        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='ZONE_STATUS_TOGGLED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=zone,
            source_obj=None
        )

        zones_data, current_user_role_from_shared = get_zones_with_status(request) # get_zones_with_status returns role

        html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role_from_shared, # Use role from shared function
            },
            request=request
        )

        response = HttpResponse(html)
        status_text = "activée" if zone.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showInfo": "Zone {zone.nom} {status_text}."}}'
        return response