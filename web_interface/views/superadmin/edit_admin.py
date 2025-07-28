from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context_and_html
from logs.utils import log_action # Importation de log_action

def edit_admin_view(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)

    if user.role == 'SUPERADMIN':
        response = HttpResponse("Action non autorisée sur un SuperAdmin.", status=403)
        response['HX-Trigger'] = '{"showError": "Action non autorisée sur un SuperAdmin."}'
        
        # MODIFICATION : Log pour tentative de modification de SuperAdmin
        log_action(
            actor_id=request.session['user_id'],
            action='SUPERADMIN_MODIFICATION_ATTEMPT',
            details=f"Tentative de modification du SuperAdmin {user.email} (ID: {user.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}).",
            target_user_id=user.pk,
            level='warning' # Ou 'error' si vous considérez cela comme plus grave
        )
        return response

    if request.method == "POST":
        # Conserver les valeurs originales pour le logging
        original_username = user.username
        original_email = user.email
        original_role = user.role
        original_zone = user.zone.nom if user.zone else "Aucune"
        original_is_active = user.is_active

        email = request.POST.get("email", "").strip()
        new_role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")
        
        # --- Début de la logique de validation et de mise à jour ---
        # Cette partie est essentielle pour déterminer ce qui a changé
        
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
            response['HX-Trigger'] = '{"showError": "Échec de la modification de l\'utilisateur."}' # Message générique pour le toast
            
            # MODIFICATION : Log pour échec de modification
            log_action(
                actor_id=request.session['user_id'],
                action='USER_MODIFICATION_FAILED',
                details=f"Échec de la modification de l'utilisateur {user.email} (ID: {user.pk}) par {request.session.get('email')} (ID: {request.session.get('user_id')}). Erreur: {validation_error_message.replace('<p>', '').replace('</p>', '')}",
                target_user_id=user.pk,
                level='warning'
            )
            return response
            
        # Mettre à jour l'utilisateur si les validations passent
        user.username = request.POST.get("username", user.username)
        user.email = email

        if new_role and new_role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            user.role = new_role
        
        if user.role in ["ADMIN_ZONE", "WS_USER"]:
            user.zone_id = zone_id
        else:
            user.zone_id = None
            
        user.save()

        # --- Logging de la modification réussie ---
        log_details = f"L'utilisateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) a modifié l'utilisateur {user.email} (ID: {user.pk})."
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
            log_details += " Aucun changement détecté." # Au cas où il n'y aurait eu aucune modification réelle

        log_action(
            actor_id=request.session['user_id'],
            action='USER_MODIFIED',
            details=log_details,
            target_user_id=user.pk,
            level='info'
        )
        # --- Fin du logging ---

        context, html_content = get_refreshed_dashboard_context_and_html(request)
        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur modifié avec succès."}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "user": user,
        "zones": zones,
        "current_user_role": request.session.get('role'),
    }
    return render(request, "superadmin/partials/form_edit.html", context)
