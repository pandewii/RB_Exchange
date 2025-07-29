# web_interface/views/admin_technique/delete_schedule.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from users.models import CustomUser # Importation nécessaire pour CustomUser
from django_celery_beat.models import PeriodicTask
from logs.utils import log_action # Importation de log_action

class DeleteScheduleView(View):
    def post(self, request, source_id):
        """
        Supprime la tâche planifiée associée à une source.
        """
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
            # MODIFICATION : Log pour accès non autorisé, utilise les IDs corrigés et current_active_user pour le message
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une planification par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=source_id)

        # MODIFICATION : Message de log sémantique avec gestion de l'impersonation
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            # Si l'acteur racine est différent de l'utilisateur effectif actuel
            if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                 details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
        else: # Pas d'impersonation, l'acteur racine est l'utilisateur actif actuel
            details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

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
                action_type = 'SCHEDULE_MANAGEMENT_FAILED' # Changed type if task not found

            source.periodic_task = None
            source.save(update_fields=["periodic_task"])
        else:
            log_details = (
                f"{details_prefix} a tenté de supprimer la planification de la source '{source.nom}' (ID: {source.pk}), mais aucune planification n'était associée."
            )
            log_level = 'warning'
            action_type = 'SCHEDULE_MANAGEMENT_FAILED'


        log_action(
            actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
            impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
            action=action_type,
            details=log_details,
            target_user_id=None,
            level=log_level,
            zone_id=source.zone.pk, # Ajout de zone_id pour un meilleur contexte de log
            source_id=source.pk # Ajout de source_id pour un meilleur contexte de log
        )

        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Planification supprimée avec succès."}'
        return response