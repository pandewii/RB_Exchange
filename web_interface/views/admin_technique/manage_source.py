# web_interface/views/admin_technique/manage_source.py

import os
# import json # Plus nécessaire ici si le subprocess est déplacé vers Celery
# import subprocess # Plus nécessaire ici si le subprocess est déplacé vers Celery
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw
from scrapers.tasks import run_scraper_for_source # Importation de la tâche Celery

def get_available_scrapers():
    try:
        # Utilise la variable SCRAPERS_DIR de settings pour la portabilité
        scraper_dir = settings.SCRAPERS_DIR
        if not os.path.isdir(scraper_dir):
            return []
        return sorted([f for f in os.listdir(scraper_dir) if f.endswith('.py') and not f.startswith('__')])
    except Exception:
        return []

class ManageSourceView(View):
    def get(self, request, *args, **kwargs):
        # Vérification du rôle est essentielle ici pour une vue non-API
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403) # Ou redirect('login')

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        source = None
        if hasattr(zone, 'source'):
            source = zone.source
        context = {
            "zone": zone,
            "source": source,
            "available_scrapers": get_available_scrapers()
        }
        return render(request, "admin_technique/partials/form_manage_source.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)
        
        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        nom = request.POST.get("nom", "").strip()
        url_source = request.POST.get("url_source", "").strip()
        scraper_filename = request.POST.get("scraper_filename", "").strip()

        if not all([nom, url_source, scraper_filename]):
            # HX-Retarget permet d'afficher l'erreur dans un élément spécifique de la modale
            response = HttpResponse('<p class="text-red-500">Tous les champs sont obligatoires.</p>')
            response['HX-Retarget'] = '#form-error-message' # Supposant un div avec cet ID dans le form_manage_source.html
            response.status_code = 400
            return response

        # Création ou mise à jour de la Source
        source, created = Source.objects.update_or_create(
            zone=zone,
            defaults={'nom': nom, 'url_source': url_source, 'scraper_filename': scraper_filename}
        )
        
        # Correction CRITIQUE: Déclenchement ASYNCHRONE du scraper via Celery
        run_scraper_for_source.delay(source.pk) # <- Appelle la tâche Celery

        # Préparation de la réponse HTMX: on rafraîchit les détails de la source
        # et on déclenche une notification indiquant que le scraping est en cours.
        context = {"zone": zone, "source": source}
        html = render_to_string("admin_technique/partials/_source_details.html", context)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source configurée. L\'exécution du scraper a été lancée en arrière-plan."}'
        # Après le déclenchement asynchrone, la table des raw_currencies ne sera pas mise à jour immédiatement.
        # Il faudra une méthode pour la rafraîchir une fois la tâche Celery terminée (via HTMX Polling ou WebSocket).
        # Pour l'instant, le message "showInfo" indique le statut.
        return response