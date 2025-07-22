from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from users.models import CustomUser
from core.models.zone_monetaire import ZoneMonetaire
from email_validator import validate_email, EmailNotValidError
# MODIFICATION : Importer la fonction shared
from .shared import get_refreshed_dashboard_context_and_html

# CORRECTION: Changer 'id' en 'pk' dans la signature de la fonction (déjà fait, laissé pour contexte)
def edit_admin_view(request, pk):
    user = get_object_or_404(CustomUser, pk=pk) # Utiliser 'pk' ici aussi

    if user.role == 'SUPERADMIN':
        response = HttpResponse("Action non autorisée sur un SuperAdmin.", status=403)
        response['HX-Trigger'] = '{"showError": "Action non autorisée sur un SuperAdmin."}' # Ajout du toast d'erreur
        return response

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        new_role = request.POST.get("role")
        zone_id = request.POST.get("zone_id")

        if new_role in ["ADMIN_ZONE", "WS_USER"] and not zone_id:
            response = HttpResponse('<p>Une zone est obligatoire pour ce rôle.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Une zone est obligatoire pour ce rôle."}' # Ajout du toast d'erreur
            return response

        if not email:
            response = HttpResponse(f'<p>Le champ email ne peut pas être vide.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Le champ email ne peut pas être vide."}' # Ajout du toast d'erreur
            return response
            
        try:
            valid_email = validate_email(email, check_deliverability=False)
            email = valid_email.email
        except EmailNotValidError as e:
            response = HttpResponse(f'<p>Adresse email invalide : {str(e)}</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Adresse email invalide."}' # Ajout du toast d'erreur
            return response

        if email != user.email and CustomUser.objects.filter(email=email).exists():
            response = HttpResponse('<p>Cet email est déjà utilisé par un autre compte.</p>')
            response['HX-Retarget'] = '#edit-form-error-message'
            response.status_code = 400
            response['HX-Trigger'] = '{"showError": "Cet email est déjà utilisé."}' # Ajout du toast d'erreur
            return response
            
        user.username = request.POST.get("username", user.username)
        user.email = email

        if new_role and new_role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            user.role = new_role
        
        # MODIFICATION : S'assurer que zone_id est défini correctement
        if new_role == "ADMIN_ZONE":
            user.zone_id = zone_id # Conserver la zone si le rôle est ADMIN_ZONE
        elif new_role == "WS_USER":
             user.zone_id = zone_id # Conserver la zone si le rôle est WS_USER
        else:
            user.zone_id = None # Supprimer la zone si le rôle n'en requiert pas

        user.save()

        # MODIFICATION : Appeler la fonction shared avec l'objet request et les filtres
        context, html_content = get_refreshed_dashboard_context_and_html(request) # context n'est pas utilisé ici directement pour le rendu
        response = HttpResponse(html_content) # Utiliser le HTML généré par la fonction shared
        response['HX-Trigger'] = '{"showSuccess": "Utilisateur modifié avec succès."}'
        return response

    zones = ZoneMonetaire.objects.all()
    # MODIFICATION : Passer 'current_user_role' au contexte du formulaire GET
    context = {
        "user": user,
        "zones": zones,
        "current_user_role": request.session.get('role'), # Passer le rôle explicitement pour le formulaire
    }
    return render(request, "superadmin/partials/form_edit.html", context)