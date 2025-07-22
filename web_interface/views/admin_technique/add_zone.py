# web_interface/views/admin_technique/add_zone.py

from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from .shared import get_zones_with_status
from logs.utils import log_action # Importation de log_action

class AddZoneView(View):
    
    def get(self, request, *args, **kwargs):
        context = {
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_add_zone.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour ajouter une zone par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
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
                "current_user_role": request.session.get('role'),
            }
            html = render_to_string("admin_technique/partials/form_add_zone.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            
            # MODIFICATION : Log pour échec de création de zone
            log_action(
                actor_id=request.session['user_id'],
                action='ZONE_CREATION_FAILED',
                details=f"Échec de la création de la zone '{nom}' par {request.session.get('email')} (ID: {request.session.get('user_id')}). Erreur: {error_message}",
                level='warning'
            )
            return response
            
        zone = ZoneMonetaire.objects.create(nom=nom) # Capturer l'objet zone créé

        # MODIFICATION : Appeler log_action avec des détails plus sémantiques
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a créé une nouvelle zone monétaire '{zone.nom}' (ID: {zone.pk})."
        )
        log_action(
            actor_id=request.session['user_id'],
            action='ZONE_CREATED',
            details=log_details,
            target_user_id=None, # Pas d'utilisateur cible direct pour une zone
            level='info'
        )

        zones_data, current_user_role = get_zones_with_status(request)
        
        updated_zones_table_html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role,
            },
            request=request
        )

        response = HttpResponse(updated_zones_table_html)
        response['HX-Retarget'] = '#zones-table-container'
        response['HX-Reswap'] = 'outerHTML'
        response['HX-Trigger'] = '{"showSuccess": "Zone créée avec succès !"}'
        return response