# web_interface/views/admin_technique/manage_source.py

import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw
from scrapers.tasks import run_scraper_for_source # Importation de la tâche Celery

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
        
        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu GET
        context = {
            "zone": zone,
            "source": source,
            "available_scrapers": get_available_scrapers(),
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
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
            # MODIFICATION : Passer 'current_user_role' au contexte de l'erreur du formulaire
            context = {
                "zone": zone,
                "source": None, # Si la source n'est pas encore créée ou si erreur, ne pas passer l'objet source
                "available_scrapers": get_available_scrapers(),
                "error_message": "Tous les champs sont obligatoires.",
                "current_user_role": request.session.get('role'), # Passer le rôle explicitement
            }
            response = HttpResponse(render_to_string("admin_technique/partials/form_manage_source.html", context, request=request), status=400)
            response['HX-Retarget'] = '#modal' # Cible la modale pour qu'elle soit remplacée avec le formulaire d'erreur
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = '{"showError": "Tous les champs sont obligatoires."}'
            return response

        source, created = Source.objects.update_or_create(
            zone=zone,
            defaults={'nom': nom, 'url_source': url_source, 'scraper_filename': scraper_filename}
        )
        
        run_scraper_for_source.delay(source.pk)

        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu du partiel
        context = {
            "zone": zone, # Pour s'assurer que la zone est dispo dans le partial
            "source": source,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source configurée. L\'exécution du scraper a été lancée en arrière-plan."}'
        return response