# web_interface/views/admin_technique/delete_source.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source, Devise # Import Devise
from core.models.activated_currency import ActivatedCurrency # Import ActivatedCurrency if needed directly for the query
from users.models import CustomUser
from django_celery_beat.models import PeriodicTask
from logs.utils import log_action

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        context = {
            "source": source,
            "current_user_role": request.session.get('role'),
        }
        return render(request, "admin_technique/partials/form_delete_source.html", context)

    def post(self, request, *args, **kwargs):
        # ... (logging impersonation logic remains the same) ...
        current_active_user_id = request.session.get('user_id')
        current_active_user = None
        if current_active_user_id:
            current_active_user = CustomUser.objects.filter(pk=current_active_user_id).first()

        actor_id_for_log = current_active_user_id
        impersonator_id_for_log = None

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']

        root_actor_obj = None
        if actor_id_for_log:
            root_actor_obj = CustomUser.objects.filter(pk=actor_id_for_log).first()

        impersonator_obj = None
        if impersonator_id_for_log:
            impersonator_obj = CustomUser.objects.filter(pk=impersonator_id_for_log).first()

        if request.session.get("role") != "ADMIN_TECH":
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une source par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}). Rôle insuffisant.",
                level='warning'
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone

        # NEW CHECK: Prevent deletion if the zone has active currencies via ActivatedCurrency model
        # The query should now be on ActivatedCurrency, filtering by zone and is_active=True
        active_currencies_count = ActivatedCurrency.objects.filter(zone=zone, is_active=True).count() #

        if active_currencies_count > 0:
            error_message = f"Impossible de supprimer la source : La zone '{zone.nom}' (ID: {zone.pk}) contient {active_currencies_count} devise(s) active(s). Veuillez désactiver toutes les devises associées à cette zone avant de supprimer la source."
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='SOURCE_DELETION_FAILED_ACTIVE_CURRENCIES',
                details=error_message,
                level='warning',
                zone_id=zone.pk,
                source_id=source.pk
            )
            context = {
                "zone": zone,
                "source": source,
                "current_user_role": request.session.get('role'),
            }
            html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        # ... (rest of the deletion and logging logic remains the same) ...
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_id:
                 details_prefix += f" et exécuté par {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"
        else:
            details_prefix = f"L'administrateur {current_active_user.email if current_active_user else 'Utilisateur inconnu'} (ID: {current_active_user_id}, Rôle: {current_active_user.get_role_display() if current_active_user else 'N/A'})"

        log_details = (
            f"{details_prefix} a supprimé la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}' (ID: {zone.pk})."
        )

        if source.periodic_task:
            log_details += f" La tâche planifiée '{source.periodic_task.name}' (ID: {source.periodic_task.pk}) a également été supprimée."
            source.periodic_task.delete()

        source.delete()

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='SOURCE_DELETED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_id=zone.pk,
            source_id=source.pk
        )

        context = {
            "zone": zone,
            "source": None,
            "current_user_role": request.session.get('role'),
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source, données associées et planification (si existante) supprimées avec succès."}'
        return response