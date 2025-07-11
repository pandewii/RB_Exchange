# web_interface/views/superadmin/delete_admin.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from users.models import CustomUser
from .shared import get_refreshed_dashboard_context_and_html

class DeleteAdminView(View):
    def get(self, request, *args, **kwargs):
        if request.session.get("role") != "SUPERADMIN":
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_to_delete = get_object_or_404(CustomUser, pk=kwargs.get('pk'))
        context = {"user_to_delete": user_to_delete}
        return render(request, "superadmin/partials/form_delete.html", context)

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "SUPERADMIN":
            return HttpResponse("Accès non autorisé.", status=403)
        
        user_id_to_delete = kwargs.get('pk')
        user_to_delete = get_object_or_404(CustomUser, pk=user_id_to_delete)

        if user_to_delete.role == 'SUPERADMIN':
            superadmins_count = CustomUser.objects.filter(role='SUPERADMIN').count()
            if superadmins_count == 1:
                error_message = "Impossible de supprimer le seul SuperAdmin du système."
            elif str(user_to_delete.pk) == str(request.session.get('user_id')):
                error_message = "Impossible de vous supprimer via cette interface."
            else:
                error_message = "Action non autorisée sur un SuperAdmin."

            if 'error_message' in locals():
                context = {
                    "user_to_delete": user_to_delete,
                    "error_message": error_message
                }
                html = render_to_string("superadmin/partials/form_delete.html", context, request=request)
                response = HttpResponse(html, status=400)
                response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
                return response

        user_to_delete.delete()

        html = get_refreshed_dashboard_context_and_html()
        response = HttpResponse(html)
        response['HX-Trigger'] = 'showSuccess'  # Déclencheur propre
        return response
