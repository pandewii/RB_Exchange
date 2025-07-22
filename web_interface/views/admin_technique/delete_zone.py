# web_interface/views/admin_technique/delete_zone.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser # Importation nécessaire pour CustomUser
# MODIFICATION : Importer la fonction shared
from .shared import get_zones_with_status

class DeleteZoneView(View):

    def get(self, request, *args, **kwargs):
        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)
        # MODIFICATION : Passer 'current_user_role' au contexte du formulaire GET
        context = {
            "zone": zone,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        return render(request, "admin_technique/partials/form_delete_zone.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)

        if zone.users.exists():
            error_message = f"Impossible de supprimer la zone '{zone.nom}' car elle est associée à des utilisateurs. Veuillez d'abord les désassocier."
            response = HttpResponse(status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        zone.delete()

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
        # CORRECTION : Utiliser le nouveau format de HX-Trigger (sans HX-Trigger-Params)
        response['HX-Trigger'] = '{"showInfo": "Zone supprimée avec succès."}'
        return response