# web_interface/views/admin_technique/toggle_zone.py

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from core.models import ZoneMonetaire
from .shared import get_zones_with_status
from logs.utils import log_action # Importation de log_action

class ToggleZoneView(View):
    def post(self, request, pk):
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer le statut d'une zone par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})
            
        zone = get_object_or_404(ZoneMonetaire, pk=pk)

        old_status = "active" if zone.is_active else "inactive"
        zone.is_active = not zone.is_active
        zone.save()
        new_status = "active" if zone.is_active else "inactive"

        # MODIFICATION : Message de log sémantique
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a basculé le statut de la zone '{zone.nom}' (ID: {zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )
        log_action(
            actor_id=request.session['user_id'],
            action='ZONE_STATUS_TOGGLED',
            details=log_details,
            target_user_id=None, # Pas d'utilisateur cible direct pour une zone
            level='info'
        )

        zones_data, current_user_role = get_zones_with_status(request)
        
        html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role,
            },
            request=request
        )
        
        response = HttpResponse(html)
        status_text = "activée" if zone.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showInfo": "Zone {zone.nom} {status_text}."}}'
        return response