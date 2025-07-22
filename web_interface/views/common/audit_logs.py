# web_interface/views/common/audit_logs.py

from django.shortcuts import render, redirect
from django.views import View
from django.db.models import Q
from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class AuditLogView(View):
    """
    Vue pour afficher l'historique détaillé des logs du système.
    Permet aux SuperAdmins et AdminTechniques de consulter les logs.
    Les AdminZones peuvent voir les logs pertinents pour leur zone.
    """
    def get(self, request, *args, **kwargs):
        user_role = request.session.get('role')
        user_id = request.session.get('user_id')

        if not user_id or user_role not in ['SUPERADMIN', 'ADMIN_TECH', 'ADMIN_ZONE']:
            return redirect('login') # Rediriger si non authentifié ou rôle non autorisé

        logs_queryset = LogEntry.objects.select_related('actor', 'impersonator', 'target_user').order_by('-timestamp')

        # Application des filtres par rôle
        if user_role == 'ADMIN_TECH':
            # Un Admin Technique peut voir tous les logs liés aux zones et sources,
            # et les logs où il est l'acteur.
            logs_queryset = logs_queryset.filter(
                Q(action__in=[
                    "ZONE_CREATED", "ZONE_MODIFIED", "ZONE_DELETED", "ZONE_STATUS_TOGGLED", "ZONE_DELETION_FAILED",
                    "SOURCE_CONFIGURED", "SOURCE_MODIFIED", "SOURCE_DELETED", "SOURCE_CONFIGURATION_FAILED",
                    "SCHEDULE_CREATED", "SCHEDULE_MODIFIED", "SCHEDULE_DELETED", "SCHEDULE_MANAGEMENT_FAILED",
                    "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED", "ALIAS_MANAGEMENT_FAILED",
                    "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR", "SCRAPER_INVALID_JSON", "SCRAPER_UNEXPECTED_ERROR",
                    "RAW_DATA_DATE_PARSE_ERROR", "RAW_DATA_VALUE_PARSE_ERROR", "PIPELINE_CALCULATION_ERROR",
                    "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START"
                ]) |
                Q(actor__pk=user_id) |
                Q(impersonator__pk=user_id)
            )

        elif user_role == 'ADMIN_ZONE':
            # Un Admin Zone ne voit que les logs liés à sa zone et les actions qu'il a effectuées.
            # Cela est plus complexe car les logs n'ont pas directement un champ zone_id.
            # Il faut filtrer par les objets liés à la zone (sources, devises activées, users de la zone).
            # Pour simplifier, nous allons commencer par les actions qu'il a initiées.
            # Un filtrage plus précis par zone nécessiterait de passer des informations de zone dans le log_entry lui-même.
            # Pour l'instant, on se concentre sur les actions directes ou ciblées.

            current_user = get_object_or_404(CustomUser, pk=user_id)
            if not current_user.zone:
                logs_queryset = LogEntry.objects.none() # Aucun log si Admin Zone sans zone
            else:
                # Logs où l'Admin Zone est l'acteur ou la cible
                logs_queryset = logs_queryset.filter(
                    Q(actor__pk=user_id) |
                    Q(impersonator__pk=user_id) | # Si quelqu'un impersonne cet AdminZone
                    Q(target_user__pk=user_id)    # Si cet AdminZone est la cible d'une action
                ).filter(
                    Q(action__in=["CURRENCY_ACTIVATION_TOGGLED"]) | # Actions spécifiques à l'Admin Zone
                    Q(details__icontains=f"Zone: {current_user.zone.nom}") # Tente de filtrer les logs par nom de zone dans les détails
                )
                # Note: Le filtrage par 'details__icontains' est moins robuste.
                # Idéalement, les LogEntry auraient une FK vers Zone si les actions sont spécifiques à une zone.


        # Application des filtres de recherche
        search_query = request.GET.get('q', '').strip()
        if search_query:
            logs_queryset = logs_queryset.filter(
                Q(action__icontains=search_query) |
                Q(details__icontains=search_query) |
                Q(actor__email__icontains=search_query) |
                Q(impersonator__email__icontains=search_query) |
                Q(target_user__email__icontains=search_query)
            )

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(logs_queryset, 20) # 20 logs par page
        try:
            logs = paginator.page(page)
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            logs = paginator.page(paginator.num_pages)

        context = {
            'logs': logs,
            'current_user_role': user_role, # Passer le rôle actuel pour le template
            'search_query': search_query,
        }
        return render(request, "common/audit_log.html", context)


# Vue pour marquer les notifications UI comme lues
class MarkUINotificationReadView(View):
    def post(self, request, pk):
        if not request.session.get('user_id'):
            return HttpResponse("Non authentifié.", status=401)
        
        notification = get_object_or_404(UINotification, pk=pk, user__pk=request.session.get('user_id'))
        notification.is_read = True
        notification.save()
        
        # Retourne simplement une réponse vide (204 No Content) ou le nouveau compte de notifications non lues.
        # HX-Trigger sera utilisé pour rafraîchir le compte de notifications non lues si une icône de cloche est présente.
        return HttpResponse(status=204)