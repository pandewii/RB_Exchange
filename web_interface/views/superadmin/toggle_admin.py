# web_interface/views/superadmin/toggle_admin.py

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from users.models import CustomUser
from django.views.decorators.http import require_http_methods
# MODIFICATION : Importer la fonction shared
from .shared import get_refreshed_dashboard_context_and_html

@require_http_methods(["POST"])
def toggle_admin_view(request, pk):
    if request.session.get("role") != "SUPERADMIN":
        return HttpResponse("Accès non autorisé.", status=403)

    user = get_object_or_404(CustomUser, pk=pk)

    if user.role == 'SUPERADMIN':
        if user.pk == request.user.pk: # Vérifier si c'est le SuperAdmin connecté
            response = HttpResponse("Impossible de désactiver votre propre compte SuperAdmin.", status=400)
            response['HX-Trigger'] = '{"showError": "Impossible de vous désactiver."}'
            return response
        
        # Si c'est un autre SuperAdmin, on peut potentiellement bloquer l'action
        # ou laisser passer si la politique le permet. Pour l'instant, on bloque.
        response = HttpResponse("Action non autorisée sur un autre SuperAdmin.", status=403)
        response['HX-Trigger'] = '{"showError": "Action non autorisée sur un SuperAdmin."}'
        return response

    user.is_active = not user.is_active
    user.save()

    status_message = "activé" if user.is_active else "désactivé"

    # MODIFICATION : Appeler la fonction shared avec l'objet request et les filtres
    context, html_content = get_refreshed_dashboard_context_and_html(request) # context n'est pas utilisé ici directement pour le rendu
    response = HttpResponse(html_content) # Utiliser le HTML généré par la fonction shared
    response['HX-Trigger'] = f'{{"showSuccess": "Utilisateur {user.email} {status_message} avec succès."}}'
    return response