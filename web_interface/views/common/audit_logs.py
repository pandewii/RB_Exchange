# web_interface/views/common/audit_logs.py

from django.shortcuts import render, redirect, get_object_or_404 
from django.views import View
from django.db.models import Q
from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.http import HttpResponse
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
            return redirect('login') 

        logs_queryset = LogEntry.objects.select_related('actor', 'impersonator', 'target_user').order_by('-timestamp')

        # Application des filtres par rôle
        if user_role == 'ADMIN_TECH':
            logs_queryset = logs_queryset.filter(
                Q(action__in=[
                    "ZONE_CREATED", "ZONE_MODIFIED", "ZONE_DELETED", "ZONE_STATUS_TOGGLED", "ZONE_DELETION_FAILED", "ZONE_PROPERTIES_UPDATE_FAILED", "ZONE_CREATION_FAILED",
                    "SOURCE_CONFIGURED", "SOURCE_MODIFIED", "SOURCE_DELETED", "SOURCE_CONFIGURATION_FAILED",
                    "SCHEDULE_CREATED", "SCHEDULE_MODIFIED", "SCHEDULE_DELETED", "SCHEDULE_MANAGEMENT_FAILED",
                    "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED", "ALIAS_MANAGEMENT_FAILED",
                    "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR", "SCRAPER_INVALID_JSON", "SCRAPER_UNEXPECTED_ERROR",
                    "RAW_DATA_DATE_PARSE_ERROR", "RAW_DATA_VALUE_PARSE_ERROR", "PIPELINE_CALCULATION_ERROR",
                    "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START",
                    "UNAUTHORIZED_ACCESS_ATTEMPT", # Admin Techs should see these too
                    "UNAUTHORIZED_DASHBOARD_ACCESS", "USER_LOGIN_FAILED_API", "USER_NOT_FOUND",
                    # Also actions on users that are AdminTechs themselves or consumers they manage if user management is part of their role.
                    # For now, stick to the provided list from the prompt which covers infrastructure.
                ]) |
                Q(actor__pk=user_id) | # If they are the root actor
                Q(impersonator__pk=user_id) # If they were the one who impersonated
            )

        elif user_role == 'ADMIN_ZONE':
            current_user = get_object_or_404(CustomUser, pk=user_id)
            if not current_user.zone:
                logs_queryset = LogEntry.objects.none() 
            else:
                # Filtrage basé sur le rôle AdminZone
                # Il faut inclure les logs où l'AdminZone est l'acteur (directement ou impersonné par quelqu'un d'autre)
                # ou si l'action concerne directement sa zone.

                # Filter based on the log's actor/impersonator fields, AND/OR details string (as a fallback)
                logs_queryset = logs_queryset.filter(
                    Q(actor__pk=user_id) | # AdminZone is the root actor
                    Q(impersonator__pk=user_id) | # AdminZone is the impersonated user for the action
                    Q(target_user__pk=user_id) | # AdminZone is the target of the action
                    Q(details__icontains=f"Zone: {current_user.zone.nom} (ID: {current_user.zone.pk})") # Specific filter for zone in details
                ).filter( # Further filter by action types relevant to AdminZone
                    Q(action__in=[
                        "CURRENCY_ACTIVATION_TOGGLED",
                        "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED", "ALIAS_MANAGEMENT_FAILED",
                        "CURRENCY_TOGGLE_FAILED_NO_ZONE"
                    ]) |
                    # AdminZone also needs to see if someone (e.g. SuperAdmin) is impersonating *them*
                    Q(action__in=["USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION"], target_user__pk=user_id) |
                    Q(action__in=["USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION"], actor__pk=user_id) # If AdminZone initiates impersonation (unlikely per rules, but for completeness)
                )


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
        paginator = Paginator(logs_queryset, 20) 
        try:
            logs = paginator.page(page)
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            logs = paginator.page(paginator.num_pages)

        context = {
            'logs': logs,
            'current_user_role': user_role, 
            'search_query': search_query,
        }
        return render(request, "common/audit_log.html", context)


class MarkUINotificationReadView(View):
    def post(self, request, pk):
        if not request.session.get('user_id'):
            return HttpResponse("Non authentifié.", status=401)
        
        notification = get_object_or_404(UINotification, pk=pk, user__pk=request.session.get('user_id'))
        notification.is_read = True
        notification.save()
        
        return HttpResponse(status=204)