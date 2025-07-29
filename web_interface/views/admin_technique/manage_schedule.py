# web_interface/views/admin_technique/manage_schedule.py

import json
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from users.models import CustomUser # Importation nécessaire pour CustomUser
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from logs.utils import log_action 

class ManageScheduleView(View):

    def post(self, request, *args, **kwargs):
        # Début de la logique pour la gestion de l'impersonation pour le log
        current_active_user_id = request.session.get('user_id')
        current_active_user = None
        if current_active_user_id:
            current_active_user = CustomUser.objects.filter(pk=current_active_user_id).first()

        actor_id_for_log = current_active_user_id 
        impersonator_id_for_log = None 

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        root_actor_obj = None
        if actor_id_for_log:
            root_actor_obj = CustomUser.objects.filter(pk=actor_id_for_log).first()
        
        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = CustomUser.objects.filter(pk=impersonator_id_for_log).first()
        # Fin de la logique pour la gestion de l'impersonation pour le log

        if request.session.get("role") != "ADMIN_TECH":
            log_action(
                actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
                impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une planification par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Rôle insuffisant.", # Message mis à jour
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

            # MODIFICATION : Message de log sémantique avec gestion de l'impersonation
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                # Si l'acteur racine est différent de l'utilisateur effectif actuel
                if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                     details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
            else: # Pas d'impersonation, l'acteur racine est l'utilisateur actif actuel
                details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

            log_details = (
                f"{details_prefix} a modifié la planification de la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk})."
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
                actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
                impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
                action='SCHEDULE_MODIFIED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_id=zone_id, 
                source_id=source_id 
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

            # MODIFICATION : Message de log sémantique avec gestion de l'impersonation
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                # Si l'acteur racine est différent de l'utilisateur effectif actuel
                if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                     details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
            else: # Pas d'impersonation, l'acteur racine est l'utilisateur actif actuel
                details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

            log_details = (
                f"{details_prefix} a créé une nouvelle planification pour la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk}). "
                f"Exécution à {hour}:{minute}, Statut: {'Activée' if enabled else 'Désactivée'}."
            )
            log_action(
                actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
                impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
                action='SCHEDULE_CREATED',
                details=log_details,
                target_user_id=None,
                level='info',
                zone_id=zone_id, 
                source_id=source_id 
            )

        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Planification enregistrée avec succès."}'
        return response