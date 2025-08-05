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

@require_http_methods(["GET", "POST"])
def add_admin_view(request):
    # Access control: Ensure user is authenticated and is a SUPERADMIN
    if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
        log_action(
            actor_id=request.user.pk if request.user.is_authenticated else None,
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            details=f"Accès non autorisé pour ajouter un administrateur par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
            level='warning'
        )
        return HttpResponse("Accès non autorisé.", status=403)

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")

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
            response = HttpResponse(f'<p>Adresse email invalide : {str(e)}</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Adresse email invalide."}'
            log_action(
                actor_id=request.user.pk,
                action='ADMIN_CREATION_FAILED',
                details=f"Échec de la création d'un administrateur par {request.user.email} (ID: {request.user.pk}). Erreur: Adresse email invalide ({email}).",
                level='warning',
                zone_obj=zone_instance_for_log,
                source_obj=None
            )
            return response

        if CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé. Veuillez en choisir un autre.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Cet email est déjà utilisé."}'
            log_action(
                actor_id=request.user.pk,
                action='ADMIN_CREATION_FAILED',
                details=f"Échec de la création d'un administrateur par {request.user.email} (ID: {request.user.pk}). Erreur: Email déjà utilisé ({email}).",
                level='warning',
                zone_obj=zone_instance_for_log,
                source_obj=None
            )
            return response

        if role == "ADMIN_ZONE" and not zone_id:
            response = HttpResponse('<p>La zone est obligatoire pour le rôle Admin Zone.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "La zone est obligatoire pour ce rôle."}'
            log_action(
                actor_id=request.user.pk,
                action='ADMIN_CREATION_FAILED',
                details=f"Échec de la création d'un administrateur par {request.user.email} (ID: {request.user.pk}). Rôle {role}, Zone non fournie.",
                level='warning',
                zone_obj=zone_instance_for_log,
                source_obj=None
            )
            return response

        final_zone_obj = None
        if zone_id:
            final_zone_obj = get_object_or_404(ZoneMonetaire, pk=zone_id)

        user = CustomUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone=final_zone_obj if role == "ADMIN_ZONE" else None
        )

        zone_name = user.zone.nom if user.zone else "N/A"
        log_details = (
            f"L'administrateur {request.user.email} (ID: {request.user.pk}, Rôle: {request.user.role}) "
            f"a créé un nouvel administrateur {user.email} (Rôle: {user.get_role_display()}"
        )
        if user.role == "ADMIN_ZONE":
            log_details += f", Zone: {zone_name})."
        else:
            log_details += ")."
        log_action(
            actor_id=request.user.pk,
            action='ADMIN_CREATED',
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
        response['HX-Trigger'] = '{"showSuccess": "Administrateur créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    context = {
        "zones": zones,
        "current_user_role": request.user.role, # Use request.user.role
    }
    return render(request, "superadmin/partials/form_add.html", context)