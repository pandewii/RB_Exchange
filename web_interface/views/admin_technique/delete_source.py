# web_interface/views/admin_technique/delete_source.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask 
from logs.utils import log_action # Importation de log_action

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_delete_source.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une source par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone 
        
        # MODIFICATION : Message de log sémantique pour suppression réussie
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a supprimé la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}' (ID: {zone.pk})."
        )

        if source.periodic_task:
            log_details += f" La tâche planifiée '{source.periodic_task.name}' (ID: {source.periodic_task.pk}) a également été supprimée."
            source.periodic_task.delete()

        source.delete()
        
        log_action(
            actor_id=request.session['user_id'],
            action='SOURCE_DELETED',
            details=log_details,
            target_user_id=None,
            level='info'
        )

        context = {
            "zone": zone,
            "source": None,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source, données associées et planification (si existante) supprimées avec succès."}'
        return response