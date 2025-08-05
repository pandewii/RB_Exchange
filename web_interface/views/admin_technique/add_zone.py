# web_interface/views/admin_technique/add_zone.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire
from users.models import CustomUser 
from .shared import get_zones_with_status
from logs.utils import log_action 

class AddZoneView(View):
    
    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour ajouter une zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,    
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

        context = {
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/partials/form_add_zone.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour ajouter une zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,    
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

        # Start impersonation logic setup for logging
        actor_id_for_log = request.user.pk
        impersonator_id_for_log = None 
        current_active_user_obj = request.user # This is already the current user after auth middleware

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Fetch actual user objects for logging details, if necessary
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log) if actor_id_for_log else None
        impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log) if impersonator_id_for_log else None
        # End impersonation logic setup

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
                "current_user_role": request.user.role, # Use request.user.role
            }
            html = render_to_string("admin_technique/partials/form_add_zone.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='ZONE_CREATION_FAILED',
                details=f"Échec de la création de la zone '{nom}' par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}). Erreur: {error_message}",
                level='warning',
                zone_obj=None, 
                source_obj=None
            )
            return response
            
        zone = ZoneMonetaire.objects.create(nom=nom) 

        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk: 
                 details_prefix += f" et exécuté par {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"
        else: 
            details_prefix = f"L'administrateur {current_active_user_obj.email} (ID: {current_active_user_obj.pk}, Rôle: {current_active_user_obj.get_role_display()})"


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
            zone_obj=zone, 
            source_obj=None
        )

        zones_data, current_user_role_from_shared = get_zones_with_status(request) # get_zones_with_status returns role
        
        updated_zones_table_html = render_to_string(
            "admin_technique/partials/_zones_table.html",
            {
                "zones_with_status": zones_data,
                "current_user_role": current_user_role_from_shared, # Use role from shared function
            },
            request=request
        )

        response = HttpResponse(updated_zones_table_html)
        response['HX-Retarget'] = '#zones-table-container'
        response['HX-Reswap'] = 'outerHTML'
        response['HX-Trigger'] = '{"showSuccess": "Zone créée avec succès !"}'
        return response