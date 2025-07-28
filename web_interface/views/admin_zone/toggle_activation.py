# web_interface/views/admin_zone/toggle_activation.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, ActivatedCurrency
from users.models import CustomUser # Assurez-vous que CustomUser est importé
from logs.utils import log_action 

class ToggleActivationView(View):
    def post(self, request, devise_code):
        # L'utilisateur dont la session est actuellement active (ex: l'Admin Zone impersonné)
        current_active_user_id = request.session.get('user_id')
        current_active_user = get_object_or_404(CustomUser, pk=current_active_user_id)

        actor_id_for_log = current_active_user_id # Par défaut: l'utilisateur actuel est l'acteur
        impersonator_id_for_log = None # Par défaut: pas d'impersonateur

        # Vérifier si une impersonation est active
        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            # L'acteur racine est le premier utilisateur dans la pile d'impersonation
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            
            # L'impersonateur est l'utilisateur dont la session était active *immédiatement avant* la session actuelle.
            # C'est le dernier utilisateur ID poussé sur la pile d'impersonation.
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Récupérer les objets utilisateur réels pour la chaîne de détails du log
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log)
        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log)


        if request.session.get("role") != "ADMIN_ZONE":
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer l'activation d'une devise par {current_active_user.email} (ID: {current_active_user.pk}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        if not current_active_user.zone:
            error_message = "Action impossible : vous n'êtes pas assigné à une zone."
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='CURRENCY_TOGGLE_FAILED_NO_ZONE', 
                details=f"Échec de bascule de l'activation de devise par {current_active_user.email} (ID: {current_active_user.pk}) car non assigné à une zone.",
                level='warning'
            )
            return HttpResponse(error_message, status=400, headers={'HX-Trigger': f'{{"showError": "{error_message}"}}'})
        
        devise = get_object_or_404(Devise, pk=devise_code)

        activation, created = ActivatedCurrency.objects.get_or_create(
            zone=current_active_user.zone,
            devise=devise
        )

        old_status = "active" if activation.is_active else "inactive"
        activation.is_active = not activation.is_active
        activation.save()
        new_status = "active" if activation.is_active else "inactive"
        
        # Construire la chaîne de détails avec les informations d'impersonation
        details_prefix = f"L'officier {root_actor_obj.email} (ID: {root_actor_obj.pk}, Rôle: {root_actor_obj.get_role_display()})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            # Si l'acteur racine est différent de l'utilisateur effectif actuel (celui dont la session est active)
            if root_actor_obj.pk != current_active_user.pk: 
                 details_prefix += f" et exécuté par {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"
        else: # Pas d'impersonation, donc l'acteur racine est l'utilisateur actif actuel
            details_prefix = f"L'administrateur {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"


        log_details = (
            f"{details_prefix} a basculé le statut de la devise '{devise.code}' (Nom: {devise.nom}) "
            f"pour la zone '{current_active_user.zone.nom}' (ID: {current_active_user.zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='CURRENCY_ACTIVATION_TOGGLED',
            details=log_details,
            target_user_id=None, 
            level='info',
            zone_id=current_active_user.zone.pk 
        )

        activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=current_active_user.zone, is_active=True)
        active_codes = set(d.devise.code for d in activated_devises_for_zone)

        context = {
            'devise': devise, 
            'active_codes': active_codes,
            'current_user_role': request.session.get('role'), 
        }
        html = render_to_string("admin_zone/partials/_currency_row.html", context, request=request)
        
        response = HttpResponse(html)
        status_text = "activée" if activation.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showSuccess": "Devise {devise.code} {status_text} avec succès."}}'
        return response
