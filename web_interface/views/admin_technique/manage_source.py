# web_interface/views/admin_technique/manage_source.py

import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw
from scrapers.tasks import run_scraper_for_source
from logs.utils import log_action 
from users.models import CustomUser # Importation nécessaire pour CustomUser

def get_available_scrapers():
    try:
        scraper_dir = settings.SCRAPERS_DIR
        if not os.path.isdir(scraper_dir):
            return []
        return sorted([f for f in os.listdir(scraper_dir) if f.endswith('.py') and not f.startswith('__')])
    except Exception:
        return []

class ManageSourceView(View):
    def get(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403) 

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        source = None
        if hasattr(zone, 'source'):
            source = zone.source
        
        context = {
            "zone": zone,
            "source": source,
            "available_scrapers": get_available_scrapers(),
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_manage_source.html", context)

    def post(self, request, *args, **kwargs):
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
            log_action(
                actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
                impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une source par {current_active_user.email} (ID: {current_active_user.pk}). Rôle insuffisant.", # Message mis à jour pour current_active_user
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403)
        
        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        nom = request.POST.get("nom", "").strip()
        url_source = request.POST.get("url_source", "").strip()
        scraper_filename = request.POST.get("scraper_filename", "").strip()

        if not all([nom, url_source, scraper_filename]):
            error_message = "Tous les champs sont obligatoires."
            context = {
                "zone": zone,
                "source": None,
                "available_scrapers": get_available_scrapers(),
                "error_message": error_message,
                "current_user_role": request.session.get('role'),
            }
            response = HttpResponse(render_to_string("admin_technique/partials/form_manage_source.html", context, request=request), status=400)
            response['HX-Retarget'] = '#modal'
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
            
            log_action(
                actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
                impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
                action='SOURCE_CONFIGURATION_FAILED',
                details=f"Échec de la configuration de la source pour la zone '{zone.nom}' (ID: {zone.pk}) par {current_active_user.email} (ID: {current_active_user.pk}). Erreur: {error_message}", # Message mis à jour
                target_user_id=None,
                level='warning',
                zone_id=zone.pk 
            )
            return response

        is_creation = not hasattr(zone, 'source')
        
        source, created = Source.objects.update_or_create(
            zone=zone,
            defaults={'nom': nom, 'url_source': url_source, 'scraper_filename': scraper_filename}
        )
        
        action_type = 'SOURCE_CONFIGURED' if is_creation else 'SOURCE_MODIFIED'
        
        # Construction du préfixe de détails avec gestion de l'impersonation
        details_prefix = f"L'administrateur {root_actor_obj.email} (ID: {root_actor_obj.pk}, Rôle: {root_actor_obj.get_role_display()})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            # Si l'acteur racine est différent de l'utilisateur effectif actuel (celui dont la session est active)
            if root_actor_obj.pk != current_active_user.pk: 
                 details_prefix += f" et exécuté par {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"
        else: # Pas d'impersonation, donc l'acteur racine est l'utilisateur actif actuel
            details_prefix = f"L'administrateur {current_active_user.email} (ID: {current_active_user.pk}, Rôle: {current_active_user.get_role_display()})"

        log_details = (
            f"{details_prefix} {'a configuré' if is_creation else 'a modifié'} la source '{source.nom}' (ID: {source.pk}) pour la zone '{zone.nom}' (ID: {zone.pk}). "
            f"Fichier scraper: {source.scraper_filename}, URL: {source.url_source}."
        )

        log_action(
            actor_id=actor_id_for_log, # Utilisation de l'acteur corrigé
            impersonator_id=impersonator_id_for_log, # Utilisation de l'impersonateur corrigé
            action=action_type,
            details=log_details,
            target_user_id=None,
            level='info',
            zone_id=zone.pk, 
            source_id=source.pk 
        )

        run_scraper_for_source.delay(source.pk)

        context = {
            "zone": zone,
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source configurée. L\'exécution du scraper a été lancée en arrière-plan."}'
        return response