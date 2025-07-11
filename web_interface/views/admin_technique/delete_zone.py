# web_interface/views/admin_technique/delete_zone.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser
from .shared import get_zones_with_status

class DeleteZoneView(View):

    def get(self, request, *args, **kwargs):
        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)
        context = {"zone": zone}
        return render(request, "admin_technique/partials/form_delete_zone.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)

        if zone.users.exists():
            error_message = f"Impossible de supprimer la zone '{zone.nom}' car elle est associée à des utilisateurs. Veuillez d'abord les désassocier."
            response = HttpResponse(status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        zone.delete()

        zones_data = get_zones_with_status()
        html = render_to_string("admin_technique/partials/_zones_table.html", {"zones_with_status": zones_data})
        
        response = HttpResponse(html)
        response['HX-Trigger'] = 'showInfo'
        response['HX-Trigger-Params'] = '{"value": "Zone supprimée avec succès."}'
        return response

        return response
