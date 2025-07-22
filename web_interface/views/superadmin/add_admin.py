# web_interface/views/superadmin/add_admin.py

from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from django.views.decorators.http import require_http_methods
from email_validator import validate_email, EmailNotValidError
# MODIFICATION : Importer la fonction shared
from .shared import get_refreshed_dashboard_context_and_html

@require_http_methods(["GET", "POST"])
def add_admin_view(request):
    # Suppression de la vérification de rôle redondante (déjà fait, laissé pour contexte)
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
            response['HX-Trigger'] = '{"showError": "Adresse email invalide."}' # Ajout du toast d'erreur
            return response

        if CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé. Veuillez en choisir un autre.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Cet email est déjà utilisé."}' # Ajout du toast d'erreur
            return response

        if role == "ADMIN_ZONE" and not zone_id:
            response = HttpResponse('<p>La zone est obligatoire pour le rôle Admin Zone.</p>')
            response['HX-Retarget'] = '#form-error-message'
            response['HX-Reswap'] = 'innerHTML'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "La zone est obligatoire pour ce rôle."}' # Ajout du toast d'erreur
            return response

        CustomUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            role=role,
            is_active=True,
            zone_id=zone_id if role == "ADMIN_ZONE" else None
        )
        
        # MODIFICATION : Appeler la fonction shared avec l'objet request et les filtres
        # Les filtres sont réinitialisés après ajout pour un affichage "propre"
        context, html_content = get_refreshed_dashboard_context_and_html(request) # context ici n'est pas utilisé directement pour le rendu
        response = HttpResponse(html_content) # Utiliser le HTML généré par la fonction shared
        response['HX-Trigger'] = '{"showSuccess": "Administrateur créé avec succès !"}'
        return response

    zones = ZoneMonetaire.objects.all()
    # MODIFICATION : Passer 'current_user_role' au contexte du formulaire GET si le formulaire utilise cette variable
    context = {
        "zones": zones,
        "current_user_role": request.session.get('role'), # Passer le rôle explicitement pour le formulaire
    }
    return render(request, "superadmin/partials/form_add.html", context)