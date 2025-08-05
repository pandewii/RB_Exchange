# web_interface/views/admin_technique/delete_source.py

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source, Devise, ZoneMonetaire
from core.models.activated_currency import ActivatedCurrency
from users.models import CustomUser
from django_celery_beat.models import PeriodicTask
from logs.utils import log_action

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour afficher le formulaire de suppression de source par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        context = {
            "source": source,
            "current_user_role": request.user.role, # Use request.user.role
        }
        return render(request, "admin_technique/partials/form_delete_source.html", context)

    def post(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and is an ADMIN_TECH
        if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
            log_action(
                actor_id=request.user.pk if request.user.is_authenticated else None,
                action='UNAUTHORIZED_ACCESS_ATTEMPT',
                details=f"Accès non autorisé pour supprimer une source par {request.user.email if request.user.is_authenticated else 'Utilisateur non authentifié'} (ID: {request.user.pk if request.user.is_authenticated else 'N/A'}). Rôle insuffisant.",
                level='warning',
                zone_obj=None,
                source_obj=None
            )
            return HttpResponse("Accès non autorisé.", status=403, headers={'HX-Trigger': '{"showError": "Accès non autorisé."}'})

        # Start impersonation logic setup for logging
        actor_id_for_log = request.user.pk
        impersonator_id_for_log = None
        current_active_user_obj = request.user # This is already the current user after auth middleware

        if 'impersonation_stack' in request.session and request.session['impersonation_stack']:
            actor_id_for_log = request.session['impersonation_stack'][0]['user_id']
            impersonator_id_for_log = request.session['impersonation_stack'][-1]['user_id']
        
        # Fetch actual user objects for logging details, if necessary
        root_actor_obj = get_object_or_404(CustomUser, pk=actor_id_for_log) if actor_id_for_log else None
        impersonator_obj = get_object_or_404(CustomUser, pk=impersonator_id_for_log) if impersonator_id_for_log else None
        # End impersonation logic setup

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone

        active_currencies_count = ActivatedCurrency.objects.filter(zone=zone, is_active=True).count()

        if active_currencies_count > 0:
            error_message = f"Impossible de supprimer la source : La zone '{zone.nom}' (ID: {zone.pk}) contient {active_currencies_count} devise(s) active(s). Veuillez désactiver toutes les devises associées à cette zone avant de supprimer la source."
            log_action(
                actor_id=actor_id_for_log,
                impersonator_id=impersonator_id_for_log,
                action='SOURCE_DELETION_FAILED_ACTIVE_CURRENCIES',
                details=error_message,
                level='warning',
                zone_obj=zone,
                source_obj=source
            )
            context = {
                "zone": zone,
                "source": source,
                "current_user_role": request.user.role, # Use request.user.role
            }
            html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)
            response = HttpResponse(html, status=400)
            response['HX-Trigger'] = f'{{"showError": "{error_message}"}}'
            return response

        # Build log details with impersonation info
        details_prefix = f"L'administrateur {root_actor_obj.email if root_actor_obj else 'Utilisateur inconnu'} (ID: {actor_id_for_log}, Rôle: {root_actor_obj.get_role_display() if root_actor_obj else 'N/A'})"
        if impersonator_obj:
            details_prefix += f" (agissant via {impersonator_obj.email} (ID: {impersonator_obj.pk}, Rôle: {impersonator_obj.get_role_display()}))"
            if root_actor_obj and root_actor_obj.pk != current_active_user_obj.pk:
                 details_prefix += f" et exécuté par {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"
        else:
            details_prefix = f"L'administrateur {current_active_user_obj.email if current_active_user_obj else 'Utilisateur inconnu'} (ID: {current_active_user_obj.pk if current_active_user_obj else 'N/A'}, Rôle: {current_active_user_obj.get_role_display() if current_active_user_obj else 'N/A'})"

        log_details = (
            f"{details_prefix} a supprimé la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}' (ID: {zone.pk})."
        )

        if source.periodic_task:
            log_details += f" La tâche planifiée '{source.periodic_task.name}' (ID: {source.periodic_task.pk}) a également été supprimée."
            source.periodic_task.delete()

        # Capture info before deletion as source object will become invalid
        source_name = source.nom
        source_pk = source.pk
        zone_name = zone.nom
        zone_pk = zone.pk

        source.delete()

        log_action(
            actor_id=actor_id_for_log,
            impersonator_id=impersonator_id_for_log,
            action='SOURCE_DELETED',
            details=log_details,
            target_user_id=None,
            level='info',
            zone_obj=ZoneMonetaire.objects.filter(pk=zone_pk).first(), # Re-fetch zone if needed for consistency, or rely on string details
            source_obj=None # Source is deleted, so pass None
        )

        context = {
            "zone": ZoneMonetaire.objects.filter(pk=zone_pk).first(), # Re-fetch zone as it's not gone
            "source": None, # Source is deleted
            "current_user_role": request.user.role, # Use request.user.role
        }
        html = render_to_string("admin_technique/partials/_source_details.html", context, request=request)

        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source, données associées et planification (si existante) supprimées avec succès."}'
        return response