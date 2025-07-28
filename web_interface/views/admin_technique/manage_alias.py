# web_interface/views/admin_technique/manage_alias.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, DeviseAlias, ScrapedCurrencyRaw
from .shared import get_daily_photocopy
from logs.utils import log_action 

class ManageAliasView(View):
    def get(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
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
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_manage_alias.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer un alias par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)

        raw_currency = get_object_or_404(ScrapedCurrencyRaw, pk=kwargs.get('raw_currency_id'))
        official_currency_code = request.POST.get('official_currency_code')

        message_type_ui = "showError" 
        message_text_ui = "Une erreur est survenue." 
        log_level = 'info'
        log_details = ""
        action_type = "ALIAS_MANAGEMENT_FAILED" # Default for errors
        
        # Capture zone_id and source_id for logging
        zone_id = raw_currency.source.zone.pk if raw_currency.source and raw_currency.source.zone else None
        source_id = raw_currency.source.pk if raw_currency.source else None


        if not official_currency_code: # Case: Delete alias
            aliases_deleted_count = 0
            
            if raw_currency.nom_devise_brut:
                aliases_deleted_count += DeviseAlias.objects.filter(alias=raw_currency.nom_devise_brut.upper()).delete()[0]
            
            if raw_currency.code_iso_brut and (raw_currency.code_iso_brut.upper() != raw_currency.nom_devise_brut.upper() if raw_currency.nom_devise_brut else True):
                aliases_deleted_count += DeviseAlias.objects.filter(alias=raw_currency.code_iso_brut.upper()).delete()[0]
            
            if aliases_deleted_count > 0:
                message_type_ui = "showInfo"
                message_text_ui = f"Alias(es) pour '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' supprimé(s) avec succès."
                log_details = (
                    f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                    f"a supprimé {aliases_deleted_count} alias pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {raw_currency.source.nom if raw_currency.source else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                action_type = "ALIAS_DELETED"
            else:
                message_type_ui = "showInfo"
                message_text_ui = "Aucun alias trouvé pour cette devise brute."
                log_details = (
                    f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                    f"a tenté de supprimer un alias mais aucun n'a été trouvé pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {raw_currency.source.nom if raw_currency.source else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                action_type = "ALIAS_MANAGEMENT_FAILED" # Indicate an attempt that didn't lead to a deletion, hence a form of failure.
                log_level = 'warning'

        else: # Case: Create or update alias
            official_currency = get_object_or_404(Devise, pk=official_currency_code)

            aliases_to_create_or_update = []
            
            if raw_currency.nom_devise_brut:
                aliases_to_create_or_update.append(raw_currency.nom_devise_brut.upper())
            
            if raw_currency.code_iso_brut:
                code_iso_upper = raw_currency.code_iso_brut.upper()
                if code_iso_upper not in aliases_to_create_or_update:
                    aliases_to_create_or_or_update.append(code_iso_upper)
            
            if not aliases_to_create_or_update:
                message_text_ui = "Aucun identifiant brut valide pour créer un alias."
                log_details = (
                    f"Échec de la gestion de l'alias par {request.session.get('email')} (ID: {request.session.get('user_id')}). "
                    f"Aucun identifiant brut valide pour la devise scrappée '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Source: {raw_currency.source.nom if raw_currency.source else 'N/A'}, Date: {raw_currency.date_publication_brut})."
                )
                log_level = 'warning'
                
                common_context_for_error = {
                    "raw_currency": raw_currency,
                    "official_currencies": Devise.objects.order_by('code'),
                    "existing_alias": DeviseAlias.objects.filter(alias=(raw_currency.nom_devise_brut or raw_currency.code_iso_brut).upper()).first(),
                    "alias_candidate": (raw_currency.nom_devise_brut or raw_currency.code_iso_brut).upper(),
                    "current_user_role": request.session.get('role'),
                    "error_message": message_text_ui # Pass error for form display
                }
                response = HttpResponse(render_to_string("admin_technique/partials/form_manage_alias.html", common_context_for_error, request=request), status=400)
                response['HX-Retarget'] = '#modal'
                response['HX-Reswap'] = 'outerHTML'
                response['HX-Trigger'] = f'{{"showError": "{message_text_ui}"}}'
                log_action(
                    actor_id=request.session['user_id'],
                    action=action_type,
                    details=log_details,
                    target_user_id=None,
                    level=log_level,
                    zone_id=zone_id, # ADDED: Pass zone_id
                    source_id=source_id # ADDED: Pass source_id
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
            action_type = "ALIAS_CREATED" if created_aliases_count > 0 else "ALIAS_MODIFIED" # More granular action
            if created_aliases_count > 0 and updated_aliases_count > 0:
                action_type = "ALIAS_CREATED_AND_MODIFIED" # Even more granular
            
            log_details = (
                f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
                f"a {('créé et/ou modifié' if created_aliases_count > 0 and updated_aliases_count > 0 else ('créé' if created_aliases_count > 0 else 'modifié'))} "
                f"l'alias pour la devise brute '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' vers la devise officielle '{official_currency.code}' "
                f"pour la source '{raw_currency.source.nom}' (ID: {raw_currency.source.pk}) dans la zone '{raw_currency.source.zone.nom}' (ID: {raw_currency.source.zone.pk})." # Added more details
            )


        log_action(
            actor_id=request.session['user_id'],
            action=action_type,
            details=log_details,
            target_user_id=None, # L'utilisateur cible n'est pas directement un user
            level=log_level,
            zone_id=zone_id, # ADDED: Pass zone_id
            source_id=source_id # ADDED: Pass source_id
        )
        
        source = raw_currency.source
        photocopy_of_the_day, aliases_dict = get_daily_photocopy(source) 

        context = {
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "close_modal": True,
            "current_user_role": request.session.get('role'),
        }
        
        html = render_to_string("admin_technique/partials/_raw_currency_table.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = f'{{"{message_type_ui}": "{message_text_ui}"}}'
        return response