# web_interface/views/admin_zone/toggle_activation.py

from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Devise, ActivatedCurrency
from users.models import CustomUser
# from .shared import get_dashboard_context # CORRECTION: Plus besoin de cette fonction si on ne rend qu'une ligne

class ToggleActivationView(View):
    def post(self, request, devise_code):
        if request.session.get("role") != "ADMIN_ZONE":
            return HttpResponse("Accès non autorisé.", status=403)

        user = get_object_or_404(CustomUser, pk=request.session.get('user_id'))
        if not user.zone:
            return HttpResponse("Action impossible : vous n'êtes pas assigné à une zone.", status=400)
        
        devise = get_object_or_404(Devise, pk=devise_code)

        activation, created = ActivatedCurrency.objects.get_or_create(
            zone=user.zone,
            devise=devise
        )

        activation.is_active = not activation.is_active
        activation.save()
        
        # CORRECTION: Récupérer le set des codes actifs pour le rendu du partial
        activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=user.zone, is_active=True)
        active_codes = set(d.devise.code for d in activated_devises_for_zone)

        # CORRECTION: Rendre uniquement le partial de la ligne de devise mise à jour
        context = {
            'devise': devise, 
            'active_codes': active_codes # Passe le set pour que le partial puisse vérifier le statut
        }
        html = render_to_string("admin_zone/partials/_currency_row.html", context)
        
        response = HttpResponse(html)
        status_text = "activée" if activation.is_active else "désactivée"
        response['HX-Trigger'] = f'{{"showSuccess": "Devise {devise.code} {status_text} avec succès."}}'
        return response