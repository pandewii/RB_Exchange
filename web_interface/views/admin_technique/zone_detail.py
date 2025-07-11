from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse # Importation nécessaire pour les réponses HTMX
from django.template.loader import render_to_string # Importation nécessaire pour les réponses HTMX
# from django.contrib import messages # CORRECTION: Plus besoin d'importer messages si l'on utilise les notifications HTMX
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw, DeviseAlias
from web_interface.views.admin_technique.shared import get_daily_photocopy # Importation complète pour éviter les conflits d'importations relatives.

class ZoneDetailView(View):
    
    def get(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return redirect("login")

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        
        source = None
        photocopy_of_the_day = []
        aliases_dict = {}

        if hasattr(zone, 'source'):
            source = zone.source
            # Assurez-vous que get_daily_photocopy est toujours valide avec les derniers changements.
            # Il doit retourner la "photocopie" et les alias.
            photocopy_of_the_day, aliases_dict = get_daily_photocopy(source)

        context = {
            "zone": zone,
            "source": source,
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
        }
        return render(request, "admin_technique/zone_detail.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            # CORRECTION: Retourner une HttpResponse avec un statut d'erreur pour HTMX
            response = HttpResponse("Accès non autorisé.", status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé."}'
            return response

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        nom = request.POST.get("nom", "").strip()
        is_active = request.POST.get("is_active") == "on" # Checkbox renvoie 'on' si cochée, ou None si non présente

        error_message = None
        if not nom:
            error_message = "Le nom de la zone ne peut pas être vide."
        elif ZoneMonetaire.objects.filter(nom__iexact=nom).exclude(pk=zone.pk).exists():
            error_message = "Une autre zone avec ce nom existe déjà."
        
        if error_message:
            # CORRECTION: Préparer la réponse HTMX pour afficher l'erreur dans le formulaire
            context = {"zone": zone, "error_message": error_message} # Passer le message d'erreur au template
            # Correction ici: Utiliser le bon nom de template
            html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request) # Rendre le formulaire avec l'erreur
            response = HttpResponse(html, status=400) # Statut 400 pour Bad Request
            response['HX-Retarget'] = '#zone-properties-container' # Cibler le conteneur principal
            response['HX-Reswap'] = 'outerHTML' # Remplacer l'ensemble du conteneur
            response['HX-Trigger'] = '{"showError": "' + error_message + '"}' # Notification d'erreur
            return response
            
        zone.nom = nom
        zone.is_active = is_active
        zone.save()

        # CORRECTION: Récupérer le contexte mis à jour pour la section des propriétés de la zone
        # Rendre uniquement le fragment de template des propriétés pour une mise à jour granulaire
        # S'assurer que le contexte envoyé au template de la partie est suffisant.
        html = render_to_string("admin_technique/partials/_zone_properties.html", {"zone": zone}, request=request) # Nouveau partial pour les propriétés

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Les propriétés de la zone ont été mises à jour avec succès."}'
        return response

