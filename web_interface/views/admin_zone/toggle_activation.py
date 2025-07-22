# web_interface/views/admin_zone/toggle_activation.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, ActivatedCurrency
from users.models import CustomUser
from logs.utils import log_action # NOUVEL AJOUT : Importation de log_action

class ToggleActivationView(View):
    def post(self, request, devise_code):
        user = get_object_or_404(CustomUser, pk=request.session.get('user_id'))
        
        # Vérification du rôle
        if request.session.get("role") != "ADMIN_ZONE":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer l'activation d'une devise par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        # Vérification d'assignation à une zone
        if not user.zone:
            error_message = "Action impossible : vous n'êtes pas assigné à une zone."
            # MODIFICATION : Log pour échec d'activation de devise (pas de zone)
            log_action(
                actor_id=request.session['user_id'],
                action='CURRENCY_TOGGLE_FAILED_NO_ZONE', # Type d'action spécifique
                details=f"Échec de bascule de l'activation de devise par {request.session.get('email')} (ID: {request.session.get('user_id')}) car non assigné à une zone.",
                level='warning'
            )
            return HttpResponse(error_message, status=400, headers={'HX-Trigger': f'{{"showError": "{error_message}"}}'})
        
        devise = get_object_or_404(Devise, pk=devise_code)

        activation, created = ActivatedCurrency.objects.get_or_create(
            zone=user.zone,
            devise=devise
        )

        old_status = "active" if activation.is_active else "inactive"
        activation.is_active = not activation.is_active
        activation.save()
        new_status = "active" if activation.is_active else "inactive"
        
        # MODIFICATION : Message de log sémantique
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a basculé le statut de la devise '{devise.code}' (Nom: {devise.nom}) "
            f"pour la zone '{user.zone.nom}' (ID: {user.zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )

        log_action(
            actor_id=request.session['user_id'],
            action='CURRENCY_ACTIVATION_TOGGLED',
            details=log_details,
            target_user_id=None, # Pas d'utilisateur cible direct
            level='info',
            zone_id=user.zone.pk # Passer l'ID de la zone pour un ciblage plus précis des notifications
        )

        activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=user.zone, is_active=True)
        active_codes = set(d.devise.code for d in activated_devises_for_zone)

        # MODIFICATION : Passer 'current_user_role' au contexte du partial
        context = {
            'devise': devise, 
            'active_codes': active_codes,
            'current_user_role': request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_zone/partials/_currency_row.html", context, request=request)
        
        response = HttpResponse(html)
        status_text = "activée" if activation.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showSuccess": "Devise {devise.code} {status_text} avec succès."}}'
        return response