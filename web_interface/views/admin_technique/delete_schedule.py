# web_interface/views/admin_technique/delete_schedule.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source, ZoneMonetaire
from users.models import CustomUser
from django_celery_beat.models import PeriodicTask
from logs.utils import log_action

class DeleteScheduleView(View):
    def post(self, request, source_id):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une planification par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

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

        source = get_object_or_404(Source, pk=source_id)
        zone = source.zone

        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                 details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
        else:
            details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

        log_details_base = (
            f"{details_prefix} a supprimé la planification de la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk})."
        )
        log_level = 'info'
        action_type = 'SCHEDULE_DELETED'

        if source.periodic_task_id:
            try:
                periodic_task = PeriodicTask.objects.get(id=source.periodic_task_id)
                log_details = log_details_base + f" La tâche Celery '{periodic_task.name}' (ID: {periodic_task.pk}) a été supprimée."
                periodic_task.delete()
            except PeriodicTask.DoesNotExist:
                log_details = log_details_base + " La tâche Celery associée n'a pas été trouvée (peut-être déjà supprimée)."
                log_level = 'warning'
                action_type = 'SCHEDULE_MANAGEMENT_FAILED'

            source.periodic_task = None
            source.save(update_fields=["periodic_task"])
        else:
            log_details = (
                f"{details_prefix} a tenté de supprimer la planification de la source '{source.nom}' (ID: {source.pk}), mais aucune planification n'était associée."
            )
            log_level = 'warning'
            action_type = 'SCHEDULE_MANAGEMENT_FAILED'


        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action=action_type,
            details=log_details,
            target_user_id=None,
            level=log_level,
            zone_obj=zone,
            source_obj=source
        )

        context = {
            "source": source,
            "current_user_role": request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Planification supprimée avec succès."}'
        return response