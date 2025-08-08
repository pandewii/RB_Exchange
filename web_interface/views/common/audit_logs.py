# web_interface/views/common/audit_logs.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Q
from logs.models import LogEntry
from users.models import CustomUser
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from core.models import ZoneMonetaire
from django.http import QueryDict

class AuditLogView(View):
    def get(self, request, *args, **kwargs):
        # Access control: Ensure user is authenticated and has an allowed role
        if not request.user.is_authenticated or request.user.role not in ['SUPERADMIN', 'ADMIN_TECH', 'ADMIN_ZONE']:
            return redirect('login')

        current_logged_in_user_obj = request.user
        user_role = request.user.role

        logs_queryset = LogEntry.objects.select_related('actor', 'impersonator', 'target_user', 'zone', 'source').order_by('-timestamp')

        search_query = request.GET.get('q', '').strip()
        if search_query:
            logs_queryset = logs_queryset.filter(
                Q(action__icontains=search_query) |
                Q(details__icontains=search_query) |
                Q(actor__email__icontains=search_query) |
                Q(impersonator__email__icontains=search_query) |
                Q(target_user__email__icontains=search_query) |
                Q(zone__nom__icontains=search_query) |
                Q(source__nom__icontains=search_query) |
                Q(currency_code__icontains=search_query)
            )

        # --- NOUVELLE LOGIQUE DE VISIBILITÉ DES LOGS BASÉE SUR VOTRE TABLEAU ---

        # Définition des actions pour chaque rôle
        admin_tech_actions = [
            'ZONE_', 'SOURCE_', 'SCHEDULE_', 'SCRAPER_MANUAL_EXECUTION_', 'PIPELINE_',
            'ALIAS_CREATED', 'ALIAS_MODIFIED',
            # Actions que l'Admin Tech doit voir même si elles sont de l'ordre de la sécurité générale
            'UNAUTHORIZED_ACCESS_ATTEMPT', 'WEB_LOGIN_SUCCESS', 'WEB_LOGIN_FAILED', 'API_LOGIN_SUCCESS', 'API_LOGIN_FAILED'
        ]
        
        admin_zone_actions = [
            'PIPELINE_', 'ALIAS_CREATED', 'ALIAS_MODIFIED', 'CURRENCY_ACTIVATION_TOGGLED',
            # Actions que l'Admin Zone doit voir même si elles sont de l'ordre de la sécurité générale
            'UNAUTHORIZED_ACCESS_ATTEMPT', 'WEB_LOGIN_SUCCESS', 'WEB_LOGIN_FAILED', 'API_LOGIN_SUCCESS', 'API_LOGIN_FAILED'
        ]
        
        # Filtre par rôle
        if user_role == 'SUPERADMIN':
            pass # SuperAdmin voit tout.

        elif user_role == 'ADMIN_TECH':
            filter_query = Q()
            for action_prefix in admin_tech_actions:
                if action_prefix.endswith('_'):
                    filter_query |= Q(action__startswith=action_prefix)
                else:
                    filter_query |= Q(action=action_prefix)
            
            logs_queryset = logs_queryset.filter(
                filter_query |
                Q(actor=current_logged_in_user_obj) |
                Q(impersonator=current_logged_in_user_obj) |
                Q(target_user=current_logged_in_user_obj)
            ).distinct()
            
            logs_queryset = logs_queryset.exclude(
                Q(action__in=['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY']) &
                Q(level='info')
            )
            
        elif user_role == 'ADMIN_ZONE':
            user_managed_zone = current_logged_in_user_obj.zone
            
            if not user_managed_zone:
                 logs_queryset = logs_queryset.filter(
                    Q(actor=current_logged_in_user_obj) |
                    Q(impersonator=current_logged_in_user_obj) |
                    Q(target_user=current_logged_in_user_obj)
                ).distinct()
            else:
                filter_query = Q(zone=user_managed_zone) & (
                    Q(action__startswith='PIPELINE_') |
                    Q(action__in=['ALIAS_CREATED', 'ALIAS_MODIFIED']) |
                    Q(action='CURRENCY_ACTIVATION_TOGGLED')
                )
                
                logs_queryset = logs_queryset.filter(
                    filter_query |
                    Q(actor=current_logged_in_user_obj) |
                    Q(impersonator=current_logged_in_user_obj) |
                    Q(target_user=current_logged_in_user_obj)
                ).distinct()

                logs_queryset = logs_queryset.exclude(
                    Q(action__in=['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY']) &
                    Q(level='info') &
                    Q(zone=user_managed_zone)
                )

        # Pagination (common for all roles)
        page = request.GET.get('page', 1)
        paginator = Paginator(logs_queryset, 20)
        try:
            logs = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            logs = paginator.page(paginator.num_pages)

        query_params = request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        base_query_string = query_params.urlencode()

        context = {
            'logs': logs,
            'current_user_role': user_role,
            'search_query': search_query,
            'base_query_string': base_query_string,
        }

        if request.headers.get('HX-Request'):
            return render(request, "common/_audit_log_table.html", context)
            
        return render(request, "common/audit_log.html", context)