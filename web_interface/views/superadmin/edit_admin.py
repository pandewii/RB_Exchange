from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context # CORRECTED IMPORT
from logs.utils import log_action
from django.template.loader import render_to_string # ADDED for rendering HTML

def edit_admin_view(request, pk):
    # Access control: Ensure user is authenticated and is a SuperAdmin
    if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
        log_action(
            actor_id=request.user.pk if request.user.is_authenticated else None,
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            details=f"Accès non autorisé pour modifier un administrateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
            level='warning'
        )
        return HttpResponse("Accès non autorisé.", status=403)

    user = get_object_or_404(CustomUser, pk=pk)

    # Determine zone object for logging based on the user being edited
    log_zone_obj = user.zone

    # SuperAdmin modification attempt specific checks
    if user.role == 'SUPERADMIN':
        response = HttpResponse("Action non autorisée sur un SuperAdmin.", status=403)
        response['HX-Trigger'] = '{"showError": "Action non autorisée sur un SuperAdmin."}'
        
        log_action(
            actor_id=request.user.pk,
            action='SUPERADMIN_MODIFICATION_ATTEMPT',
            details=f"Tentative de modification du SuperAdmin {user.email} (ID: {user.pk}) par {request.user.email} (ID: {request.user.pk}).",
            target_user_id=user.pk,
            level='warning', 
            zone_obj=log_zone_obj, 
            source_obj=None
        )
        return response

    if request.method == "POST":
        original_username = user.username
        original_email = user.email
        original_role = user.role
        original_zone = user.zone.nom if user.zone else "Aucune"
        # original_is_active = user.is_active # Not modified in this view, so no need to track

        email = request.POST.get("email", "").strip()
        new_role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")
        
        validation_error_message = None

        if new_role in ["ADMIN_ZONE", "WS_USER"] and not zone_id:
            validation_error_message = '<p>Une zone est obligatoire pour ce rôle.</p>'
        elif not email:
            validation_error_message = f'<p>Le champ email ne peut pas être vide.</p>'
        else:
            try:
                valid_email = validate_email(email, check_deliverability=False)
                email = valid_email.email
            except EmailNotValidError as e:
                validation_error_message = f'<p>Adresse email invalide : {str(e)}</p>'

            if not validation_error_message and email != user.email and CustomUser.objects.filter(email=email).exists():
                validation_error_message = '<p>Cet email est déjà utilisé par un autre compte.</p>'
        
        if validation_error_message:
            response = HttpResponse(validation_error_message)
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Échec de la modification de l\'utilisateur."}' 
            
            temp_zone_obj = None
            if zone_id and zone_id.isdigit():
                try:
                    temp_zone_obj = ZoneMonetaire.objects.get(pk=zone_id)
                except ZoneMonetaire.DoesNotExist:
                    pass 

            log_action(
                actor_id=request.user.pk,
                action='USER_MODIFICATION_FAILED',
                details=f"Échec de la modification de l'utilisateur {user.email} (ID: {user.pk}) par {request.user.email} (ID: {request.user.pk}). Erreur: {validation_error_message.replace('<p>', '').replace('</p>', '')}",
                target_user_id=user.pk,
                level='warning',
                zone_obj=temp_zone_obj or log_zone_obj, 
                source_obj=None
            )
            return response
            
        user.username = request.POST.get("username", user.username)
        user.email = email

        if new_role and new_role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            user.role = new_role
            if new_role in ["ADMIN_ZONE", "WS_USER"]:
                user.zone_id = zone_id # This should be the ID
            else:
                user.zone_id = None 
        
        user.save()

        log_zone_obj_after_save = user.zone

        log_details = (
            f"L'utilisateur {request.user.email} (ID: {request.user.pk}, Rôle: {request.user.role}) "
            f"a modifié l'utilisateur {user.email} (ID: {user.pk})."
        )
        changes = []
        if original_username != user.username:
            changes.append(f"Nom d'utilisateur: '{original_username}' -> '{user.username}'")
        if original_email != user.email:
            changes.append(f"Email: '{original_email}' -> '{user.email}'")
        if original_role != user.role:
            changes.append(f"Rôle: '{original_role}' -> '{user.get_role_display()}'")
        
        new_zone_name = user.zone.nom if user.zone else "Aucune"
        if original_role in ["ADMIN_ZONE", "WS_USER"] or user.role in ["ADMIN_ZONE", "WS_USER"]:
            if original_zone != new_zone_name:
                changes.append(f"Zone: '{original_zone}' -> '{new_zone_name}'")
        
        if changes:
            log_details += " Changements: " + "; ".join(changes) + "."
        else:
            log_details += " Aucun changement détecté." 

        log_action(
            actor_id=request.user.pk,
            action='USER_MODIFIED',
            details=log_details,
            target_user_id=user.pk,
            level='info',
            zone_obj=log_zone_obj_after_save, 
            source_obj=None
        )

        # Correctly call the shared function to get context only, then render HTML
        dashboard_context = get_refreshed_dashboard_context(request, '', 'all', 'all', 'all') # Pass current filters or defaults
        dashboard_context.update({
            "all_zones": ZoneMonetaire.objects.all(), # Needed for filter dropdowns in dashboard.html partial
            "current_user_role": request.user.role,
        })
        html_content = render_to_string("superadmin/partials/_full_dashboard_content.html", dashboard_context, request=request)

        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur modifié avec succès."}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "user": user,
        "zones": zones,
        "current_user_role": request.user.role, # Use request.user.role
    }
    return render(request, "superadmin/partials/form_edit.html", context)