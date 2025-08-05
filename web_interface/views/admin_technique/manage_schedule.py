# web_interface/views/admin_technique/manage_schedule.py

import json
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source, ZoneMonetaire
from users.models import CustomUser
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from logs.utils import log_action

class ManageScheduleView(View):

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une planification par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
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

        source = get_object_or_404(Source, pk=kwargs.get('source_id'))
        zone = source.zone

        hour = request.POST.get('hour', '7')
        minute = request.POST.get('minute', '0')
        enabled = request.POST.get('enabled') == 'on'

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        task_kwargs = json.dumps({'source_id': source.pk})

        if source.periodic_task:
            task = source.periodic_task
            
            old_hour = task.crontab.hour if task.crontab else 'N/A'
            old_minute = task.crontab.minute if task.crontab else 'N/A'
            old_enabled = task.enabled
            
            task.crontab = schedule
            task.interval = None
            task.enabled = enabled
            task.kwargs = task_kwargs
            task.save()

            # Build log details with impersonation info
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                     details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
            else:
                details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

            log_details = (
                f"{details_prefix} a modifié la planification de la source '{source.nom}' (ID: {source.pk}) pour la zone '{zone.nom}' (ID: {zone.pk})."
            )
            changes = []
            if old_hour != hour or old_minute != minute:
                changes.append(f"Heure: '{old_hour}:{old_minute}' -> '{hour}:{minute}'")
            if old_enabled != enabled:
                changes.append(f"Statut d'activation: {'Activée' if old_enabled else 'Désactivée'} -> {'Activée' if enabled else 'Désactivée'}")
            
            if changes:
                log_details += " Changements: " + "; ".join(changes) + "."
            else:
                log_details += " Aucun changement détecté."

            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='SCHEDULE_MODIFIED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_obj=zone,
                source_obj=source
            )

        else: # Creation of new schedule
            task_name = f"Scraper pour Source ID {source.pk} - {source.nom}"
            task = PeriodicTask.objects.create(
                crontab=schedule,
                name=task_name,
                task='scrapers.tasks.run_scraper_for_source',
                kwargs=task_kwargs,
                enabled=enabled
            )
            source.periodic_task = task
            source.save()

            # Build log details with impersonation info
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                     details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
            else:
                details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

            log_details = (
                f"{details_prefix} a créé une nouvelle planification pour la source '{source.nom}' (ID: {source.pk}) pour la zone '{zone.nom}' (ID: {zone.pk}). "
                f"Exécution à {hour}:{minute}, Statut: {'Activée' if enabled else 'Désactivée'}."
            )
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='SCHEDULE_CREATED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_obj=zone,
                source_obj=source
            )

        context = {
            "source": source,
            "current_user_role": request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Planification enregistrée avec succès."}'
        return response