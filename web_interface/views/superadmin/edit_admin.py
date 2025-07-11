from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from email_validator import validate_email, EmailNotValidError
from .shared import get_refreshed_dashboard_context_and_html

# CORRECTION: Changer 'id' en 'pk' dans la signature de la fonction
def edit_admin_view(request, pk):
    # CORRECTION: Suppression de la vérification de rôle redondante
    # if request.session.get("role") != "SUPERADMIN":
    #     return HttpResponse("Accès non autorisé.", status=403)
        
    user = get_object_or_404(CustomUser, pk=pk) # CORRECTION: Utiliser 'pk' ici aussi

    if user.role == 'SUPERADMIN':
        return HttpResponse("Action non autorisée sur un SuperAdmin.", status=403)

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        new_role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")

        if new_role in ["ADMIN_ZONE", "WS_USER"] and not zone_id:
            response = HttpResponse('<p>Une zone est obligatoire pour ce rôle.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            return response

        if not email:
            response = HttpResponse(f'<p>Le champ email ne peut pas être vide.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            return response
            
        try:
            valid_email = validate_email(email, check_deliverability=False)
            email = valid_email.email
        except EmailNotValidError as e:
            response = HttpResponse(f'<p>Adresse email invalide : {str(e)}</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            return response

        if email != user.email and CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé par un autre compte.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            return response
            
        user.username = request.POST.get("username", user.username)
        user.email = email

        if new_role and new_role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            user.role = new_role
        
        if user.role in ["ADMIN_ZONE", "WS_USER"]:
            user.zone_id = zone_id
        else:
            user.zone_id = None
            
        user.save()

        html = get_refreshed_dashboard_context_and_html()
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur modifié avec succès."}'
        return response

    zones = ZoneMonetaire.objects.all()
    # CORRECTION: Utiliser 'user.pk' pour le nom de l'utilisateur dans le template
    return render(request, "superadmin/partials/form_edit.html", {"user": user, "zones": zones})