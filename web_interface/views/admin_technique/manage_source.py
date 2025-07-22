# web_interface/views/admin_technique/manage_source.py

import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw
from scrapers.tasks import run_scraper_for_source
from logs.utils import log_action # Importation de log_action

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
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour gérer une source par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
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
            # MODIFICATION : Log pour échec de configuration de source
            log_action(
                actor_id=request.session['user_id'],
                action='SOURCE_CONFIGURATION_FAILED',
                details=f"Échec de la configuration de la source pour la zone '{zone.nom}' (ID: {zone.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}). Erreur: {error_message}",
                target_user_id=None,
                level='warning'
            )
            return response

        # Déterminer si c'est une création ou une modification pour le log
        is_creation = not hasattr(zone, 'source')
        
        source, created = Source.objects.update_or_create(
            zone=zone,
            defaults={'nom': nom, 'url_source': url_source, 'scraper_filename': scraper_filename}
        )
        
        # MODIFICATION : Message de log sémantique pour succès de configuration
        action_type = 'SOURCE_CONFIGURED' if is_creation else 'SOURCE_MODIFIED'
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"{'a configuré' if is_creation else 'a modifié'} la source '{source.nom}' (ID: {source.pk}) pour la zone '{zone.nom}' (ID: {zone.pk}). "
            f"Fichier scraper: {source.scraper_filename}, URL: {source.url_source}."
        )

        log_action(
            actor_id=request.session['user_id'],
            action=action_type,
            details=log_details,
            target_user_id=None,
            level='info'
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