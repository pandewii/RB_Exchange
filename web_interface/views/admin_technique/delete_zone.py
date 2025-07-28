# web_interface/views/admin_technique/delete_zone.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser
from .shared import get_zones_with_status
from logs.utils import log_action # Importation de log_action

class DeleteZoneView(View):

    def get(self, request, *args, **kwargs):
        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)
        context = {
            "zone": zone,
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_delete_zone.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une zone par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        zone_pk = kwargs.get('pk')
        zone = get_object_or_404(ZoneMonetaire, pk=zone_pk)

        if zone.users.exists():
            error_message = f"Impossible de supprimer la zone '{zone.nom}' car elle est associée à des utilisateurs. Veuillez d'abord les désassocier."
            # MODIFICATION : Log pour échec de suppression de zone à cause d'utilisateurs
            log_action(
                actor_id=request.session['user_id'],
                action='ZONE_DELETION_FAILED',
                details=f"Échec de la suppression de la zone '{zone.nom}' (ID: {zone.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}) car elle est associée à des utilisateurs.",
                target_user_id=None, # Pas d'utilisateur cible direct pour une zone
                level='warning'
            )
            response = HttpResponse(status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        # MODIFICATION : Message de log sémantique pour suppression réussie
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a supprimé la zone monétaire '{zone.nom}' (ID: {zone.pk})."
        )
        zone.delete()
        log_action(
            actor_id=request.session['user_id'],
            action='ZONE_DELETED',
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
        response['HX-Trigger'] = '{"showInfo": "Zone supprimée avec succès."}'
        return response
