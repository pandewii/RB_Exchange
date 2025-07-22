from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import ZoneMonetaire, Source, ScrapedCurrencyRaw, DeviseAlias
from web_interface.views.admin_technique.shared import get_daily_photocopy
from logs.utils import log_action # Importation de log_action

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
            photocopy_of_the_day, aliases_dict = get_daily_photocopy(source)

        context = {
            "zone": zone,
            "source": source,
            "raw_currencies": photocopy_of_the_day,
            "aliases_dict": aliases_dict,
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/zone_detail.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            # MODIFICATION : Log pour accès non autorisé
            log_action(
                actor_id=request.session['user_id'],
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour modifier les propriétés de zone par {request.session.get('email')} (ID: {request.session.get('user_id')}). Rôle insuffisant.",
                level='warning'
            )
            response = HttpResponse("Accès non autorisé.", status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé."}'
            return response

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
            context = {"zone": zone, "error_message": error_message, "current_user_role": request.session.get('role')}
            html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Retarget'] = '#zone-properties-container'
            response['HX-Reswap'] = 'outerHTML'
            response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
            # MODIFICATION : Log pour échec de mise à jour des propriétés de zone
            log_action(
                actor_id=request.session['user_id'],
                action='ZONE_PROPERTIES_UPDATE_FAILED',
                details=f"Échec de la mise à jour des propriétés de la zone '{original_nom}' (ID: {zone.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}). Erreur: {error_message}",
                target_user_id=None,
                level='warning'
            )
            return response
            
        zone.nom = nom
        zone.is_active = is_active
        zone.save()

        # MODIFICATION : Message de log sémantique pour mise à jour réussie
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a modifié les propriétés de la zone '{original_nom}' (ID: {zone.pk})."
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
            actor_id=request.session['user_id'],
            action='ZONE_PROPERTIES_UPDATED',
            details=log_details,
            target_user_id=None,
            level='info'
        )

        context = {
            "zone": zone,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_zone_properties.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Les propriétés de la zone ont été mises à jour avec succès."}'
        return response