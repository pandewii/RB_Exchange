# web_interface/views/admin_technique/add_zone.py

from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
# MODIFICATION : Importer la fonction shared
from .shared import get_zones_with_status

class AddZoneView(View):
    
    def get(self, request, *args, **kwargs):
        # MODIFICATION : Passer 'current_user_role' au contexte du formulaire GET
        context = {
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        return render(request, "admin_technique/partials/form_add_zone.html", context)

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
            context = {
                "error_message": error_message,
                "nom_prefill": nom,
                "current_user_role": request.session.get('role'), # Passer le rôle explicitement
            }
            html = render_to_string("admin_technique/partials/form_add_zone.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response
            
        ZoneMonetaire.objects.create(nom=nom)

        # MODIFICATION : Appeler la fonction shared avec l'objet request
        # Et déstructurer les résultats : zones_data ET current_user_role
        zones_data, current_user_role = get_zones_with_status(request)
        
        # MODIFICATION : Passer le contexte complet au template
        updated_zones_table_html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role, # Passer le rôle explicitement
            },
            request=request
        )

        response = HttpResponse(updated_zones_table_html)
        response['HX-Retarget'] = '#zones-table-container'
        response['HX-Reswap'] = 'outerHTML'
        response['HX-Trigger'] = '{"showSuccess": "Zone créée avec succès !"}'
        return response