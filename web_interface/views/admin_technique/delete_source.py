# web_interface/views/admin_technique/delete_source.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask # Importation nécessaire

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        return render(request, "admin_technique/partials/form_delete_source.html", {"source": source})

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'}) # Ajout du toast d'erreur

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone # On garde une référence à la zone avant de supprimer la source
        
        # AJOUT : Supprimer la PeriodicTask associée si elle existe
        if source.periodic_task:
            source.periodic_task.delete() # Supprime la tâche planifiée de la DB Celery Beat

        # En supprimant la source, Django va automatiquement supprimer en cascade
        # toutes les ScrapedCurrencyRaw qui lui sont liées, grâce au on_delete=models.CASCADE.
        source.delete()

        context = {"zone": zone, "source": None}
        html = render_to_string("admin_technique/partials/_source_details.html", context)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source, données associées et planification (si existante) supprimées avec succès."}' # Message plus précis
        return response