# web_interface/views/admin_technique/manage_schedule.py

import json
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from logs.utils import log_action 

class ManageScheduleView(View):

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une planification par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=kwargs.get('source_id'))
        
        hour = request.POST.get('hour', '7')
        minute = request.POST.get('minute', '0')
        enabled = request.POST.get('enabled') == 'on'

        # Capture zone_id and source_id for logging
        zone_id = source.zone.pk if source.zone else None
        source_id = source.pk

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

            log_details = (
                f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                f"a modifié la planification de la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk})." # Added zone details
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
                actor_id=request.session['user_id'],
                action='SCHEDULE_MODIFIED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_id=zone_id, # Pass zone_id
                source_id=source_id # Pass source_id
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

            log_details = (
                f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                f"a créé une nouvelle planification pour la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk}). " # Added zone details
                f"Exécution à {hour}:{minute}, Statut: {'Activée' if enabled else 'Désactivée'}."
            )
            log_action(
                actor_id=request.session['user_id'],
                action='SCHEDULE_CREATED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_id=zone_id, # Pass zone_id
                source_id=source_id # Pass source_id
            )

        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Planification enregistrée avec succès."}'
        return response
