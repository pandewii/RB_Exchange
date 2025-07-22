# web_interface/views/admin_technique/delete_schedule.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask  # Importation essentielle

class DeleteScheduleView(View):
    def post(self, request, source_id):
        """
        Supprime la tâche planifiée associée à une source.
        """
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=source_id)

        if source.periodic_task_id:
            try:
                periodic_task = PeriodicTask.objects.get(id=source.periodic_task_id)
                periodic_task.delete()
            except PeriodicTask.DoesNotExist:
                pass  # Déjà supprimée ou incohérente

            # Nettoyer la relation sur le modèle Source
            source.periodic_task = None
            source.save(update_fields=["periodic_task"])

        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu du partiel
        context = {
            "source": source, # La source est toujours nécessaire pour le partial
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Planification supprimée avec succès."}'
        return response