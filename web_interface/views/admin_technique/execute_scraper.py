# web_interface/views/admin_technique/execute_scraper.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from core.models import Source, ZoneMonetaire
from users.models import CustomUser
from scrapers.tasks import run_scraper_for_source
from logs.utils import log_action

class ExecuteScraperView(View):
    def post(self, request, source_id):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour exécuter manuellement un scraper par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        # Start impersonation logic setup for logging
        actor_id_for_log = request.user.pk
        impersonator_id_for_log = None
        current_active_user_obj = request.user # This is already the current user after auth middleware

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Fetch actual user objects for logging details, if necessary
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log) if actor_id_for_log else None
        impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log) if impersonator_id_for_log else None
        # End impersonation logic setup

        source = get_object_or_404(Source, pk=source_id)
        zone = source.zone

        # Lancement de la tâche Celery d'exécution du scraper
        try:
            run_scraper_for_source.delay(source.pk)
            message_type_ui = "showSuccess"
            message_text_ui = f"Exécution manuelle du scraper pour '{source.nom}' lancée avec succès en arrière-plan."
            log_level = 'info'
            action_type = 'SCRAPER_MANUAL_EXECUTION_STARTED'

            # Construction du message de log
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                     details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
            else:
                details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

            log_details = (
                f"{details_prefix} a lancé manuellement l'exécution du scraper pour la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}' (ID: {zone.pk})."
            )

        except Exception as e:
            message_type_ui = "showError"
            message_text_ui = f"Échec du lancement de l'exécution du scraper : {e}"
            log_level = 'error'
            action_type = 'SCRAPER_MANUAL_EXECUTION_FAILED'

            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                     details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
            else:
                details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

            log_details = (
                f"{details_prefix} a échoué à lancer manuellement l'exécution du scraper pour la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}' (ID: {zone.pk}). Erreur: {e}"
            )


        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action=action_type,
            details=log_details,
            target_user_id=None,
            level=log_level,
            zone_obj=zone,
            source_obj=source
        )
        
        response = HttpResponse(status=204)
        response['HX-Trigger'] = f'{{"{message_type_ui}": "{message_text_ui}"}}'
        return response