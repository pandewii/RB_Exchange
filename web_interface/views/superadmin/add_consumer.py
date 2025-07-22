from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from django.views.decorators.http import require_http_methods
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context_and_html
from logs.utils import log_action # Importation de log_action

@require_http_methods(["GET", "POST"])
def add_consumer_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        zone_id = request.POST.get("zone_id")
        role = "WS_USER" # Role fixe pour les consommateurs

        validation_error_message = None
        
        try:
            valid_email = validate_email(email, check_deliverability=False)
            email = valid_email.email
        except EmailNotValidError as e:
            validation_error_message = f'Adresse email invalide : {str(e)}'
        
        if not validation_error_message and CustomUser.objects.filter(email=email).exists():
            validation_error_message = 'Cet email est déjà utilisé.'

        if not validation_error_message and not zone_id:
            validation_error_message = 'La sélection d\'une zone est obligatoire.'

        if validation_error_message:
            response = HttpResponse(f'<p>{validation_error_message}</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "' + validation_error_message + '"}'
            
            # MODIFICATION : Log pour échec de création de consommateur
            log_action(
                actor_id=request.session['user_id'],
                action='CONSUMER_CREATION_FAILED',
                details=f"Échec de la création d'un consommateur par {request.session.get('email')} (ID: {request.session.get('user_id')}). Erreur: {validation_error_message}",
                level='warning'
            )
            return response
            
        user = CustomUser.objects.create( # Capturer l'objet utilisateur créé
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone_id=zone_id
        )
        
        # MODIFICATION : Appeler log_action avec des détails plus sémantiques
        zone_name = user.zone.nom if user.zone else "N/A"
        log_details = (
            f"L'administrateur {request.session.get('email')} (ID: {request.session.get('user_id')}, Rôle: {request.session.get('role')}) "
            f"a créé un nouvel utilisateur final/système {user.email} (Rôle: {user.get_role_display()}, Zone: {zone_name})."
        )
        
        log_action(
            actor_id=request.session['user_id'],
            action='CONSUMER_CREATED',
            details=log_details,
            target_user_id=user.pk, # L'utilisateur nouvellement créé est la cible
            level='info'
        )

        context, html_content = get_refreshed_dashboard_context_and_html(request)
        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur final/Système créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "zones": zones,
        "current_user_role": request.session.get('role'),
    }
    return render(request, "superadmin/partials/form_add_consumer.html", context)