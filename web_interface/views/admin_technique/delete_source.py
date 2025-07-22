# web_interface/views/admin_technique/delete_source.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask 

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        # MODIFICATION : Passer 'current_user_role' au contexte du formulaire GET
        context = {
            "source": source,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        return render(request, "admin_technique/partials/form_delete_source.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone 
        
        if source.periodic_task:
            source.periodic_task.delete()

        source.delete()

        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu du partiel
        # Lorsque la source est supprimée, le contexte "source" devient None.
        context = {
            "zone": zone, # La zone est toujours nécessaire pour le partial
            "source": None, # La source est supprimée
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source, données associées et planification (si existante) supprimées avec succès."}'
        return response