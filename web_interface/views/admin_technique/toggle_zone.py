# web_interface/views/admin_technique/toggle_zone.py

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from core.models import ZoneMonetaire
# MODIFICATION : Importer la fonction shared
from .shared import get_zones_with_status

class ToggleZoneView(View):
    def post(self, request, pk):
        if request.session.get("role") != "ADMIN_TECH":
            # CORRECTION : Retourner un toast d'erreur
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})
            
        zone = get_object_or_404(ZoneMonetaire, pk=pk)
        zone.is_active = not zone.is_active
        zone.save()

        # MODIFICATION : Appeler la fonction shared avec l'objet request
        # Et déstructurer les résultats : zones_data ET current_user_role
        zones_data, current_user_role = get_zones_with_status(request)
        
        # MODIFICATION : Passer le contexte complet au template
        html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role, # Passer le rôle explicitement
            },
            request=request
        )
        
        response = HttpResponse(html)
        status_text = "activée" if zone.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showInfo": "Zone {zone.nom} {status_text}."}}'
        return response