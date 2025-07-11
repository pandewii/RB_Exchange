# web_interface/views/admin_technique/manage_alias.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, DeviseAlias, ScrapedCurrencyRaw
from .shared import get_daily_photocopy

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
        }
        # CORRECTION: Supprimer 'request=request' car déjà passé en premier argument
        return render(request, "admin_technique/partials/form_manage_alias.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        raw_currency = get_object_or_404(ScrapedCurrencyRaw, pk=kwargs.get('raw_currency_id'))
        official_currency_code = request.POST.get('official_currency_code')

        message_type = "showError" 
        message_text = "Une erreur est survenue." 

        if not official_currency_code: 
            aliases_deleted_count = 0
            
            if raw_currency.nom_devise_brut:
                aliases_deleted_count += DeviseAlias.objects.filter(alias=raw_currency.nom_devise_brut.upper()).delete()[0]
            
            if raw_currency.code_iso_brut and (raw_currency.code_iso_brut.upper() != raw_currency.nom_devise_brut.upper() if raw_currency.nom_devise_brut else True):
                aliases_deleted_count += DeviseAlias.objects.filter(alias=raw_currency.code_iso_brut.upper()).delete()[0]
            
            if aliases_deleted_count > 0:
                message_type = "showInfo"
                message_text = f"Alias(es) pour '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' supprimé(s) avec succès."
            else:
                message_type = "showInfo"
                message_text = "Aucun alias trouvé pour cette devise brute."
            
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
                response = HttpResponse('<div id="form-error-message">Aucun identifiant brut valide pour créer un alias.</div>')
                response['HX-Retarget'] = '#form-error-message'
                response.status_code = 400
                return response

            for alias_str in aliases_to_create_or_update:
                DeviseAlias.objects.update_or_create(
                    alias=alias_str,
                    defaults={'devise_officielle': official_currency}
                )
            message_type = "showSuccess"
            message_text = "Alias(es) enregistré(s) avec succès."
        
        source = raw_currency.source
        photocopy_of_the_day, aliases_dict = get_daily_photocopy(source) 

        context = {
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "close_modal": True 
        }
        
        # Le render_to_string dans le POST est correct car il rend un fragment HTML
        html = render_to_string("admin_technique/partials/_raw_currency_table.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = f'{{"{message_type}": "{message_text}"}}'
        return response