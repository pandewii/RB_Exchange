from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw, DeviseAlias
from web_interface.views.admin_technique.shared import get_daily_photocopy
from logs.utils import log_action 
from users.models import CustomUser 

class ZoneDetailView(View):
    
    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            return redirect("login")

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk'))
        
        source = None
        photocopy_of_the_day = []
        aliases_dict = {}

        if hasattr(zone, 'source') and zone.source:
            source = zone.source
            photocopy_of_the_day, aliases_dict = get_daily_photocopy(source)

        context = {
            "zone": zone,
            "source": source,
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/zone_detail.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour modifier les propriétés de la zone par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            response = HttpResponse("Accès non autorisé.", status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé."}'
            return response

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

        zone = get_object_or_404(ZoneMonetaire, pk=kwargs.get('pk')) 

        nom = request.POST.get("nom", "").strip()
        is_active = request.POST.get("is_active") == "on" 

        original_nom = zone.nom
        original_is_active = zone.is_active

        error_message = None
        if not nom:
            error_message = "Le nom de la zone ne peut pas être vide."
        elif ZoneMonetaire.objects.filter(nom__iexact=nom).exclude(pk=zone.pk).exists():
            error_message = "Une autre zone avec ce nom existe déjà."
        
        if error_message:
            context = {"zone": zone, "error_message": error_message, "current_user_role": request.user.role} # Use request.user.role
            html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Retarget'] = '#zone-properties-container'
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='ZONE_PROPERTIES_UPDATE_FAILED',
                details=f"Échec de la mise à jour des propriétés de la zone '{original_nom}' (ID: {zone.pk}) par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}). Erreur: {error_message}",
                target_user_id=None,
                level='warning',
                zone_obj=zone, 
                source_obj=None
            )
            return response
            
        zone.nom = nom
        zone.is_active = is_active
        zone.save()

        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                 details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
        else:
            details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"


        log_details = (
            f"{details_prefix} a modifié les propriétés de la zone '{original_nom}' (ID: {zone.pk})."
        )
        changes = []
        if original_nom != zone.nom:
            changes.append(f"Nom: '{original_nom}' -> '{zone.nom}'")
        if original_is_active != zone.is_active:
            status_old = "active" if original_is_active else "inactive"
            status_new = "active" if zone.is_active else "inactive"
            changes.append(f"Statut: '{status_old}' -> '{status_new}'")
        
        if changes:
            log_details += " Changements: " + "; ".join(changes) + "."
        else:
            log_details += " Aucun changement détecté." 

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='ZONE_PROPERTIES_UPDATED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=zone, 
            source_obj=None
        )

        context = {
            "zone": zone,
            "current_user_role": request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Les propriétés de la zone ont été mises à jour avec succès."}'
        return response