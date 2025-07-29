# web_interface/views/admin_technique/execute_scraper.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from core.models import Source
from users.models import CustomUser # Importation nécessaire pour CustomUser
from scrapers.tasks import run_scraper_for_source # Importation de la tâche Celery
from logs.utils import log_action # Importation de log_action

class ExecuteScraperView(View):
    def post(self, request, source_id):
        # Début de la logique pour la gestion de l'impersonation pour le log
        current_active_user_id = request.session.get('user_id')
        current_active_user = None
        if current_active_user_id:
            current_active_user = CustomUser.objects.filter(pk=current_active_user_id).first()

        actor_id_for_log = current_active_user_id 
        impersonator_id_for_log = None 

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        root_actor_obj = None
        if actor_id_for_log:
            root_actor_obj = CustomUser.objects.filter(pk=actor_id_for_log).first()
        
        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = CustomUser.objects.filter(pk=impersonator_id_for_log).first()
        # Fin de la logique pour la gestion de l'impersonation pour le log

        # Vérification des autorisations
        if request.session.get("role") != "ADMIN_TECH":
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour exécuter manuellement un scraper par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        source = get_object_or_404(Source, pk=source_id)
        
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
                if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                     details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
            else: 
                details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

            log_details = (
                f"{details_prefix} a lancé manuellement l'exécution du scraper pour la source '{source.nom}' (ID: {source.pk}) de la zone '{source.zone.nom}' (ID: {source.zone.pk})."
            )

        except Exception as e:
            message_type_ui = "showError"
            message_text_ui = f"Échec du lancement de l'exécution du scraper : {e}"
            log_level = 'error'
            action_type = 'SCRAPER_MANUAL_EXECUTION_FAILED'

            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                     details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
            else: 
                details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

            log_details = (
                f"{details_prefix} a échoué à lancer manuellement l'exécution du scraper pour la source '{source.nom}' (ID: {source.pk}) de la zone '{source.zone.nom}' (ID: {source.zone.pk}). Erreur: {e}"
            )


        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action=action_type,
            details=log_details,
            target_user_id=None,
            level=log_level,
            zone_id=source.zone.pk,
            source_id=source.pk
        )
        
        response = HttpResponse(status=204) # Pas de HTML à retourner, juste une notification
        response['HX-Trigger'] = f'{{"{message_type_ui}": "{message_text_ui}"}}'
        return response