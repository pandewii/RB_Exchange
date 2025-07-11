from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from users.models import CustomUser
from .shared import get_refreshed_dashboard_context_and_html

@require_POST
# CORRECTION: Changer 'id' en 'pk' dans la signature de la fonction
def toggle_admin_view(request, pk):
    # CORRECTION: Suppression de la vérification de rôle redondante
    # if request.session.get("role") != "SUPERADMIN":
    #     return HttpResponse("Accès non autorisé.", status=403)
        
    user = get_object_or_404(CustomUser, pk=pk) # CORRECTION: Utiliser 'pk' ici aussi

    if user.role == 'SUPERADMIN':
        return HttpResponse("Action non autorisée sur un SuperAdmin.", status=403)

    user.is_active = not user.is_active
    user.save()

    html = get_refreshed_dashboard_context_and_html()
    response = HttpResponse(html)
    status_text = "activé" if user.is_active else "désactivé"
    response['HX-Trigger'] = f'{{"showInfo": "Utilisateur {status_text} avec succès."}}'
    return response