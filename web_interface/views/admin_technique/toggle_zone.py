# web_interface/views/admin_technique/toggle_zone.py

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from core.models import ZoneMonetaire
from users.models import CustomUser # Importation nécessaire pour CustomUser
from .shared import get_zones_with_status
from logs.utils import log_action # Importation de log_action

class ToggleZoneView(View):
    def post(self, request, pk):
        # Début de la logique pour la gestion de l'impersonation pour le log
        current_active_user_id = request.session.get('user_id')
        current_active_user = get_object_or_404(CustomUser, pk=current_active_user_id)

        actor_id_for_log = current_active_user_id 
        impersonator_id_for_log = None 

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log)
        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log)
        # Fin de la logique pour la gestion de l'impersonation pour le log

        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé, utilise les IDs corrigés
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer le statut d'une zone par {current_active_user.email} (ID: {current_active_user.pk}). Rôle insuffisant.", # Utilise current_active_user
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})
            
        zone = get_object_or_404(ZoneMonetaire, pk=pk)

        old_status = "active" if zone.is_active else "inactive"
        zone.is_active = not zone.is_active
        zone.save()
        new_status = "active" if zone.is_active else "inactive"

        # MODIFICATION : Message de log sémantique avec gestion de l'impersonation
        details_prefix = f"L'administrateur {root_actor_obj.email} (ID: {root_actor_obj.pk}, Rôle: {root_actor_obj.get_role_display()})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            # Si l'acteur racine est différent de l'utilisateur effectif actuel
            if root_actor_obj.pk != current_active_user.pk: 
                 details_prefix += f" et exécuté par {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"
        else: # Pas d'impersonation, l'acteur racine est l'utilisateur actif actuel
            details_prefix = f"L'administrateur {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"


        log_details = (
            f"{details_prefix} a basculé le statut de la zone '{zone.nom}' (ID: {zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )
        log_action(
            actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
            impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
            action='ZONE_STATUS_TOGGLED',
            details=log_details,
            target_user_id=None, # Pas d'utilisateur cible direct pour une zone
            level='info',
            zone_id=zone.pk # Ajout de zone_id pour un meilleur contexte de log
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