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
from users.models import CustomUser 

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
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour afficher le formulaire de gestion de source par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403) 

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        source = None
        if hasattr(zone, 'source') and zone.source:
            source = zone.source
        
        context = {
            "zone": zone,
            "source": source,
            "available_scrapers": get_available_scrapers(),
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/partials/form_manage_source.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une source par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)
        
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
                "current_user_role": request.user.role, # Use request.user.role
            }
            response = HttpResponse(render_to_string("admin_technique/partials/form_manage_source.html", context, request=request), status=400)
            response['HX-Retarget'] = '#modal'
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
            
            log_action(
                actor_id=actor_id_for_log, 
                impersonator_id=impersonator_id_for_log,
                action='SOURCE_CONFIGURATION_FAILED',
                details=f"Échec de la configuration de la source pour la zone '{zone.nom}' (ID: {zone.pk}) par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}). Erreur: {error_message}",
                target_user_id=None,
                level='warning',
                zone_obj=zone, 
                source_obj=None 
            )
            return response

        is_creation = not hasattr(zone, 'source') 
        
        source, created = Source.objects.update_or_create(
            zone=zone, 
            defaults={'nom': nom, 'url_source': url_source, 'scraper_filename': scraper_filename}
        )
        
        action_type = 'SOURCE_CONFIGURED' if is_creation else 'SOURCE_MODIFIED'
        
        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk: 
                 details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
        else: 
            details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

        log_details = (
            f"{details_prefix} {'a configuré' if is_creation else 'a modifié'} la source '{source.nom}' (ID: {source.pk}) pour la zone '{zone.nom}' (ID: {zone.pk}). "
            f"Fichier scraper: {source.scraper_filename}, URL: {source.url_source}."
        )

        log_action(
            actor_id=actor_id_for_log, 
            impersonator_id=impersonator_id_for_log, 
            action=action_type,
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=zone, 
            source_obj=source 
        )

        # Trigger scraper execution in background
        run_scraper_for_source.delay(source.pk)

        context = {
            "zone": zone,
            "source": source,
            "current_user_role": request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source configurée. L\'exécution du scraper a été lancée en arrière-plan."}'
        return response