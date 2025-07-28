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
def add_admin_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")

        try:
            valid_email = validate_email(email, check_deliverability=False)
            email = valid_email.email
        except EmailNotValidError as e:
            response = HttpResponse(f'<p>Adresse email invalide : {str(e)}</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML' 
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Adresse email invalide."}'
            return response

        if CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé. Veuillez en choisir un autre.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML' 
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Cet email est déjà utilisé."}'
            return response

        if role == "ADMIN_ZONE" and not zone_id:
            response = HttpResponse('<p>La zone est obligatoire pour le rôle Admin Zone.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "La zone est obligatoire pour ce rôle."}'
            return response

        user = CustomUser.objects.create( # Capturer l'objet utilisateur créé
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone_id=zone_id if role == "ADMIN_ZONE" else None
        )
        
        # MODIFICATION : Appeler log_action avec des détails plus sémantiques
        zone_name = user.zone.nom if user.zone else "N/A"
        log_details = (
            f"L'administrateur {request.session.get('email')} ({request.session.get('role')}) "
            f"a créé un nouvel administrateur {user.email} (Rôle: {user.get_role_display()}"
        )
        if user.role == "ADMIN_ZONE":
            log_details += f", Zone: {zone_name})."
        else:
            log_details += ")."

        log_action(
            actor_id=request.session['user_id'],
            action='ADMIN_CREATED',
            details=log_details,
            target_user_id=user.pk, # L'utilisateur nouvellement créé est la cible
            level='info'
        )
        
        context, html_content = get_refreshed_dashboard_context_and_html(request)
        response = HttpResponse(html_content)
        response['HX-Trigger'] = '{"showSuccess": "Administrateur créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "zones": zones,
        "current_user_role": request.session.get('role'),
    }
    return render(request, "superadmin/partials/form_add.html", context)
