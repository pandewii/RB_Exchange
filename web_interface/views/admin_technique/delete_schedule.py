# web_interface/views/admin_technique/delete_schedule.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask
from logs.utils import log_action # Importation de log_action

class DeleteScheduleView(View):
    def post(self, request, source_id):
        """
        Supprime la tâche planifiée associée à une source.
        """
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une planification par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=source_id)

        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a supprimé la planification de la source '{source.nom}' (ID: {source.pk}) pour la zone '{source.zone.nom}' (ID: {source.zone.pk})."
        )
        log_level = 'info'
        action_type = 'SCHEDULE_DELETED'

        if source.periodic_task_id:
            try:
                periodic_task = PeriodicTask.objects.get(id=source.periodic_task_id)
                log_details += f" La tâche Celery '{periodic_task.name}' (ID: {periodic_task.pk}) a été supprimée."
                periodic_task.delete()
            except PeriodicTask.DoesNotExist:
                log_details += " La tâche Celery associée n'a pas été trouvée (peut-être déjà supprimée)."
                log_level = 'warning'
                action_type = 'SCHEDULE_MANAGEMENT_FAILED' # Changed type if task not found

            source.periodic_task = None
            source.save(update_fields=["periodic_task"])
        else:
            log_details = (
                f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                f"a tenté de supprimer la planification de la source '{source.nom}' (ID: {source.pk}), mais aucune planification n'était associée."
            )
            log_level = 'warning'
            action_type = 'SCHEDULE_MANAGEMENT_FAILED'


        log_action(
            actor_id=request.session['user_id'],
            action=action_type,
            details=log_details,
            target_user_id=None,
            level=log_level
        )

        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Planification supprimée avec succès."}'
        return response
