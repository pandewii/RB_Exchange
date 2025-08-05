# web_interface/views/admin_technique/manage_alias.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, DeviseAlias, ScrapedCurrencyRaw, ZoneMonetaire, Source 
from .shared import get_daily_photocopy
from logs.utils import log_action 
from users.models import CustomUser 
from django.db.models import Q 

class ManageAliasView(View):
    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour afficher le formulaire de gestion d'alias par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

        raw_currency = get_object_or_404(ScrapedCurrencyRaw, pk=kwargs.get('raw_currency_id'))
        
        alias_candidate_raw = raw_currency.nom_devise_brut or raw_currency.code_iso_brut
        
        existing_alias = None
        if alias_candidate_raw:
            existing_alias = DeviseAlias.objects.filter(alias=alias_candidate_raw.upper()).first()
        
        context = {
            "raw_currency": raw_currency,
            "official_currencies": Devise.objects.order_by('code'),
            "existing_alias": existing_alias,
            "alias_candidate": alias_candidate_raw.upper() if alias_candidate_raw else '',
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/partials/form_manage_alias.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer un alias par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
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

        raw_currency = get_object_or_404(ScrapedCurrencyRaw, pk=kwargs.get('raw_currency_id'))
        
        zone_obj_for_log = raw_currency.source.zone if raw_currency.source and raw_currency.source.zone else None
        source_obj_for_log = raw_currency.source if raw_currency.source else None

        official_currency_code = request.POST.get('official_currency_code')

        message_type_ui = "showError" 
        message_text_ui = "Une erreur est survenue." 
        log_level = 'info'
        log_details = ""
        action_type = "ALIAS_MANAGEMENT_FAILED" 
        

        if not official_currency_code: 
            aliases_deleted_count = 0
            
            aliases_to_delete_q = Q()
            if raw_currency.nom_devise_brut:
                aliases_to_delete_q |= Q(alias=raw_currency.nom_devise_brut.upper())
            
            if raw_currency.code_iso_brut:
                code_iso_upper = raw_currency.code_iso_brut.upper()
                if not (raw_currency.nom_devise_brut and raw_currency.nom_devise_brut.upper() == code_iso_upper):
                    aliases_to_delete_q |= Q(alias=code_iso_upper)
            
            if aliases_to_delete_q: 
                aliases_deleted_count = DeviseAlias.objects.filter(aliases_to_delete_q).delete()[0]
            
            if aliases_deleted_count > 0:
                message_type_ui = "showInfo"
                message_text_ui = f"Alias(es) pour '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' supprimé(s) avec succès."
                log_details = (
                    f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'}) "
                    f"a supprimé {aliases_deleted_count} alias pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {source_obj_for_log.nom if source_obj_for_log else 'N/A'}, Zone: {zone_obj_for_log.nom if zone_obj_for_log else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                action_type = "ALIAS_DELETED"
            else:
                message_type_ui = "showInfo" 
                message_text_ui = "Aucun alias trouvé pour cette devise brute."
                log_details = (
                    f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'}) "
                    f"a tenté de supprimer un alias mais aucun n'a été trouvé pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {source_obj_for_log.nom if source_obj_for_log else 'N/A'}, Zone: {zone_obj_for_log.nom if zone_obj_for_log else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                action_type = "ALIAS_MANAGEMENT_FAILED"
                log_level = 'warning'

        else: 
            official_currency = get_object_or_404(Devise, pk=official_currency_code)

            aliases_to_create_or_update = []
            
            if raw_currency.nom_devise_brut:
                aliases_to_create_or_update.append(raw_currency.nom_devise_brut.upper())
            
            if raw_currency.code_iso_brut:
                code_iso_upper = raw_currency.code_iso_brut.upper()
                if code_iso_upper not in aliases_to_create_or_update: 
                    aliases_to_create_or_update.append(code_iso_upper)
            
            if not aliases_to_create_or_update:
                message_text_ui = "Aucun identifiant brut valide pour créer un alias."
                log_details = (
                    f"Échec de la gestion de l'alias par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}). "
                    f"Aucun identifiant brut valide pour la devise scrappée '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {source_obj_for_log.nom if source_obj_for_log else 'N/A'}, Zone: {zone_obj_for_log.nom if zone_obj_for_log else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                log_level = 'warning'
                
                common_context_for_error = {
                    "raw_currency": raw_currency,
                    "official_currencies": Devise.objects.order_by('code'),
                    "existing_alias": DeviseAlias.objects.filter(alias=(raw_currency.nom_devise_brut or raw_currency.code_iso_brut).upper()).first(),
                    "alias_candidate": (raw_currency.nom_devise_brut or raw_currency.code_iso_brut).upper(),
                    "current_user_role": request.user.role, # Use request.user.role
                    "error_message": message_text_ui 
                }
                response = HttpResponse(render_to_string("admin_technique/partials/form_manage_alias.html", common_context_for_error, request=request), status=400)
                response['HX-Retarget'] = '#modal'
                response['HX-Reswap'] = 'outerHTML'
                response['HX-Trigger'] = f'{{"showError": "{message_text_ui}"}}'
                
                log_action(
                    actor_id=actor_id_for_log,
                    impersonator_id=impersonator_id_for_log,
                    action=action_type,
                    details=log_details,
                    target_user_id=None,
                    level=log_level,
                    zone_obj=zone_obj_for_log, 
                    source_obj=source_obj_for_log 
                )
                return response

            created_aliases_count = 0
            updated_aliases_count = 0
            for alias_str in aliases_to_create_or_update:
                obj, created = DeviseAlias.objects.update_or_create(
                    alias=alias_str,
                    defaults={'devise_officielle': official_currency}
                )
                if created:
                    created_aliases_count += 1
                else:
                    updated_aliases_count += 1
            
            message_type_ui = "showSuccess"
            message_text_ui = "Alias(es) enregistré(s) avec succès."
            action_type = "ALIAS_CREATED" if created_aliases_count > 0 else "ALIAS_MODIFIED" 
            if created_aliases_count > 0 and updated_aliases_count > 0:
                action_type = "ALIAS_CREATED_AND_MODIFIED" 
            
            # Build log details with impersonation info
            details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
            if impersonator_obj:
                details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
                if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                     details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
            else:
                details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"


            log_details = (
                f"{details_prefix} {('a créé et/ou modifié' if created_aliases_count > 0 and updated_aliases_count > 0 else ('a créé' if created_aliases_count > 0 else 'a modifié'))} "
                f"l'alias pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' vers la devise officielle '{official_currency.code}' "
                f"pour la source '{source_obj_for_log.nom if source_obj_for_log else 'N/A'}' (ID: {source_obj_for_log.pk if source_obj_for_log else 'N/A'}) dans la zone '{zone_obj_for_log.nom if zone_obj_for_log else 'N/A'}' (ID: {zone_obj_for_log.pk if zone_obj_for_log else 'N/A'})."
            )

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action=action_type,
            details=log_details,
            target_user_id=None, 
            level=log_level,
            zone_obj=zone_obj_for_log, 
            source_obj=source_obj_for_log 
        )
        
        source = raw_currency.source 
        photocopy_of_the_day, aliases_dict = get_daily_photocopy(source) 

        context = {
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "close_modal": True,
            "current_user_role": request.user.role, # Use request.user.role
        }
        
        html = render_to_string("admin_technique/partials/_raw_currency_table.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = f'{{"{message_type_ui}": "{message_text_ui}"}}'
        return response