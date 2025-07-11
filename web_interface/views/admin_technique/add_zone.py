# web_interface/views/admin_technique/add_zone.py

from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from .shared import get_zones_with_status

class AddZoneView(View):
    
    def get(self, request, *args, **kwargs):
        return render(request, "admin_technique/partials/form_add_zone.html")

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        nom = request.POST.get("nom", "").strip()
        error_message = None

        if not nom:
            error_message = "Le nom de la zone ne peut pas être vide."
        elif ZoneMonetaire.objects.filter(nom__iexact=nom).exists():
            error_message = "Une zone avec ce nom existe déjà."
        
        if error_message:
            # En cas d'erreur, renvoyer le formulaire mis à jour pour être affiché dans la modale.
            context = {
                "error_message": error_message,
                "nom_prefill": nom
            }
            html = render_to_string("admin_technique/partials/form_add_zone.html", context, request=request)
            response = HttpResponse(html, status=400) # Statut 400 pour Bad Request
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}' 
            # HTMX prendra en compte le hx-target="#modal" du formulaire et le remplacera.
            return response
            
        # Si pas d'erreur, créer la zone
        ZoneMonetaire.objects.create(nom=nom)

        zones_data = get_zones_with_status()
        updated_zones_table_html = render_to_string("admin_technique/partials/_zones_table.html", {"zones_with_status": zones_data}, request=request)

        response = HttpResponse(updated_zones_table_html)
        # CORRECTION: Utiliser HX-Retarget et HX-Reswap pour mettre à jour le tableau principal
        # Cette combinaison permet de mettre à jour un élément hors de la cible du formulaire.
        response['HX-Retarget'] = '#zones-table-container' 
        response['HX-Reswap'] = 'outerHTML' 
        # Déclencher la notification de succès qui, par le JS global, fermera aussi la modale.
        response['HX-Trigger'] = '{"showSuccess": "Zone créée avec succès !"}' 
        return response