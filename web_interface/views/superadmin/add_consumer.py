from django.shortcuts import render, get_object_or_404
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from django.views.decorators.http import require_http_methods
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context # CORRECTED IMPORT
from logs.utils import log_action
from django.template.loader import render_to_string # ADDED for rendering HTML
from core.models import ZoneMonetaire # Needed for fetching all zones for dashboard context


@require_http_methods(["GET", "POST"])
def add_consumer_view(request):
    # Access control: Ensure user is authenticated and is a SUPERADMIN
    if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
        log_action(
            actor_id=request.user.pk if request.user.is_authenticated else None,
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            details=f"Accès non autorisé pour ajouter un consommateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
            level='warning'
        )
        return HttpResponse("Accès non autorisé.", status=403)

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        zone_id = request.POST.get("zone_id")
        role = "WS_USER" # Role fixe pour les consommateurs

        validation_error_message = None
        
        zone_instance_for_log = None
        if zone_id:
            try:
                zone_instance_for_log = get_object_or_404(ZoneMonetaire, pk=zone_id)
            except Exception:
                pass 

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
            
            log_action(
                actor_id=request.user.pk,
                action='CONSUMER_CREATION_FAILED',
                details=f"Échec de la création d'un consommateur par {request.user.email} (ID: {request.user.pk}). Erreur: {validation_error_message}",
                level='warning',
                zone_obj=zone_instance_for_log, 
                source_obj=None
            )
            return response
        
        final_zone_obj = get_object_or_404(ZoneMonetaire, pk=zone_id) 

        user = CustomUser.objects.create( 
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone=final_zone_obj 
        )
        
        zone_name = user.zone.nom if user.zone else "N/A"
        log_details = (
            f"L'administrateur {request.user.email} (ID: {request.user.pk}, Rôle: {request.user.role}) "
            f"a créé un nouvel utilisateur final/système {user.email} (Rôle: {user.get_role_display()}, Zone: {zone_name})."
        )
        
        log_action(
            actor_id=request.user.pk,
            action='CONSUMER_CREATED',
            details=log_details,
            target_user_id=user.pk, 
            level='info',
            zone_obj=user.zone, 
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
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur final/Système créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "zones": zones,
        "current_user_role": request.user.role, # Use request.user.role
    }
    return render(request, "superadmin/partials/form_add_consumer.html", context)