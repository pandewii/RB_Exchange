from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from django.views.decorators.http import require_http_methods
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context_and_html

@require_http_methods(["GET", "POST"])
def add_admin_view(request):
    # CORRECTION: Suppression de la vérification de rôle redondante
    # if request.session.get("role") != "SUPERADMIN":
    #     return HttpResponse("Accès non autorisé.", status=403)

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
            return response

        if CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé. Veuillez en choisir un autre.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML' 
            response.status_code = 400
            return response

        if role == "ADMIN_ZONE" and not zone_id:
            response = HttpResponse('<p>La zone est obligatoire pour le rôle Admin Zone.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            return response

        CustomUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone_id=zone_id if role == "ADMIN_ZONE" else None
        )
        
        html = get_refreshed_dashboard_context_and_html()
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Administrateur créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    return render(request, "superadmin/partials/form_add.html", {"zones": zones})