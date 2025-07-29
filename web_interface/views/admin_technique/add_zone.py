# web_interface/views/admin_technique/add_zone.py

from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser # Importation nécessaire pour CustomUser
from .shared import get_zones_with_status
from logs.utils import log_action # Importation de log_action

class AddZoneView(View):
    
    def get(self, request, *args, **kwargs):
        context = {
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_add_zone.html", context)

    def post(self, request, *args, **kwargs):
        # Début de la logique pour la gestion de l'impersonation pour le log
        current_active_user_id = request.session.get('user_id')
        current_active_user = None
        if current_active_user_id:
            current_active_user = CustomUser.objects.filter(pk=current_active_user_id).first()

        actor_id_for_log = current_active_user_id 
        impersonator_id_for_log = None 

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        root_actor_obj = None
        if actor_id_for_log:
            root_actor_obj = CustomUser.objects.filter(pk=actor_id_for_log).first()
        
        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = CustomUser.objects.filter(pk=impersonator_id_for_log).first()
        # Fin de la logique pour la gestion de l'impersonation pour le log

        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé, utilise les IDs corrigés et current_active_user pour le message
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour ajouter une zone par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Rôle insuffisant.",
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
            
            # MODIFICATION : Log pour échec de création de zone, utilise les IDs corrigés
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='ZONE_CREATION_FAILED',
                details=f"Échec de la création de la zone '{nom}' par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Erreur: {error_message}",
                level='warning'
            )
            return response
            
        zone = ZoneMonetaire.objects.create(nom=nom) # Capturer l'objet zone créé

        # MODIFICATION : Appeler log_action avec des détails plus sémantiques et IDs corrigés
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            # Si l'acteur racine est différent de l'utilisateur effectif actuel
            if root_actor_obj and root_actor_obj.pk != current_active_user_id: 
                 details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
        else: # Pas d'impersonation, l'acteur racine est l'utilisateur actif actuel
            details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"


        log_details = (
            f"{details_prefix} a créé une nouvelle zone monétaire '{zone.nom}' (ID: {zone.pk})."
        )
        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='ZONE_CREATED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_id=zone.pk # Ajout de zone_id pour un meilleur contexte de log
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