from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw, DeviseAlias
# MODIFICATION : Importer get_daily_photocopy depuis shared
from web_interface.views.admin_technique.shared import get_daily_photocopy 

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
            # get_daily_photocopy ne prend pas 'request'
            photocopy_of_the_day, aliases_dict = get_daily_photocopy(source)

        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu GET
        context = {
            "zone": zone,
            "source": source,
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        return render(request, "admin_technique/zone_detail.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            response = HttpResponse("Accès non autorisé.", status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé."}'
            return response

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        nom = request.POST.get("nom", "").strip()
        is_active = request.POST.get("is_active") == "on" 

        error_message = None
        if not nom:
            error_message = "Le nom de la zone ne peut pas être vide."
        elif ZoneMonetaire.objects.filter(nom__iexact=nom).exclude(pk=zone.pk).exists():
            error_message = "Une autre zone avec ce nom existe déjà."
        
        if error_message:
            # MODIFICATION : Passer 'current_user_role' au contexte de l'erreur du formulaire
            context = {
                "zone": zone,
                "error_message": error_message,
                "current_user_role": request.session.get('role'), # Passer le rôle explicitement
            }
            html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Retarget'] = '#zone-properties-container'
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
            return response
            
        zone.nom = nom
        zone.is_active = is_active
        zone.save()

        # MODIFICATION : Passer 'current_user_role' au contexte du formulaire mis à jour
        context = {
            "zone": zone,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Les propriétés de la zone ont été mises à jour avec succès."}'
        return response