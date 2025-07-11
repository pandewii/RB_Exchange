# web_interface/views/admin_technique/toggle_zone.py

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View # CORRECTION: Importer View
from core.models import ZoneMonetaire
from .shared import get_zones_with_status

# CORRECTION: Convertir la fonction en classe View
class ToggleZoneView(View):
    def post(self, request, pk): # Acceptera uniquement les requêtes POST
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)
            
        zone = get_object_or_404(ZoneMonetaire, pk=pk)
        zone.is_active = not zone.is_active
        zone.save()

        # On utilise la fonction partagée pour le rafraîchissement
        zones_data = get_zones_with_status()
        html = render_to_string("admin_technique/partials/_zones_table.html", {"zones_with_status": zones_data})
        
        response = HttpResponse(html)
        status_text = "activée" if zone.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showInfo": "Zone {zone.nom} {status_text}."}}'
        return response