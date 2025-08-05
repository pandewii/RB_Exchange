# web_interface/views/admin_zone/toggle_activation.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, ActivatedCurrency, ZoneMonetaire
from users.models import CustomUser
from logs.utils import log_action

class ToggleActivationView(View):
    def post(self, request, devise_code):
        # Access control: Ensure user is authenticated and is an ADMIN_ZONE
        if not request.user.is_authenticated or request.user.role != "ADMIN_ZONE":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour basculer l'activation d'une devise par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        # Start impersonation logic setup for logging
        actor_id_for_log = request.user.pk # Default to current user's PK
        impersonator_id_for_log = None
        current_active_user_obj = request.user # This is already the current user after auth middleware

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Fetch actual user objects for logging details, if necessary
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log) if actor_id_for_log else None
        impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log) if impersonator_id_for_log else None
        # End impersonation logic setup

        # Get the zone object for logging (it's current_active_user_obj.zone)
        log_zone_obj = current_active_user_obj.zone

        if not current_active_user_obj.zone:
            error_message = "Action impossible : vous n'êtes pas assigné à une zone."
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='CURRENCY_TOGGLE_FAILED_NO_ZONE',
                details=f"Échec de bascule de l'activation de devise par {current_active_user_obj.email} (ID: {current_active_user_obj.pk}) car non assigné à une zone.",
                level='warning',
                zone_obj=log_zone_obj,
                source_obj=None
            )
            return HttpResponse(error_message, status=400, headers={'HX-Trigger': f'{{"showError": "{error_message}"}}'})
        
        devise = get_object_or_404(Devise, pk=devise_code)

        activation, created = ActivatedCurrency.objects.get_or_create(
            zone=current_active_user_obj.zone,
            devise=devise
        )

        old_status = "active" if activation.is_active else "inactive"
        activation.is_active = not activation.is_active
        activation.save()
        new_status = "active" if activation.is_active else "inactive"
        
        # Build log details with impersonation info
        details_prefix = f"L'officier {root_actor_obj.email} (ID: {root_actor_obj.pk}, Rôle: {root_actor_obj.get_role_display()})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj.pk != current_active_user_obj.pk:
                 details_prefix += f" et exécuté par {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"
        else:
            details_prefix = f"L'administrateur {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"


        log_details = (
            f"{details_prefix} a basculé le statut de la devise '{devise.code}' (Nom: {devise.nom}) "
            f"pour la zone '{current_active_user_obj.zone.nom}' (ID: {current_active_user_obj.zone.pk}) "
            f"de '{old_status}' à '{new_status}'."
        )

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='CURRENCY_ACTIVATION_TOGGLED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=log_zone_obj,
            source_obj=None
        )

        activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=current_active_user_obj.zone, is_active=True)
        active_codes = set(d.devise.code for d in activated_devises_for_zone)

        context = {
            'devise': devise,
            'active_codes': active_codes,
            'current_user_role': request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_zone/partials/_currency_row.html", context, request=request)
        
        response = HttpResponse(html)
        status_text = "activée" if activation.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showSuccess": "Devise {devise.code} {status_text} avec succès."}}'
        return response