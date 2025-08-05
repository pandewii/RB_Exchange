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

        # Start with all logs, ordered by timestamp
        logs_queryset = LogEntry.objects.select_related('actor', 'impersonator', 'target_user', 'zone', 'source').order_by('-timestamp')

        # Apply search filter (common to all roles)
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
                Q(currency_code__icontains=search_query) # Search on currency_code as well
            )

        # --- Role-Based Log Visibility Logic ---

        if user_role == 'SUPERADMIN':
            # SuperAdmin sees all logs. No further filtering based on role needed.
            pass

        elif user_role == 'ADMIN_TECH':
            admin_tech_user = current_logged_in_user_obj

            logs_queryset = logs_queryset.filter(
                # Always see their own direct actions (actor, impersonator, target)
                Q(actor=admin_tech_user) |
                Q(impersonator=admin_tech_user) |
                Q(target_user=admin_tech_user) |
                # All errors/warnings/criticals (system-wide, as they need to fix them)
                Q(level__in=['error', 'critical', 'warning']) |
                # Specific pipeline execution results (success/failure/blocking events)
                Q(action__in=[
                    'PIPELINE_EXECUTION_SUCCESS', 'PIPELINE_EXECUTION_COMPLETED', # Confirmation of success
                    'PIPELINE_ERROR', 'PIPELINE_UNEXPECTED_ERROR', 'PIPELINE_CALCULATION_ERROR', # Core pipeline failures
                    'SCRAPER_TIMEOUT', 'SCRAPER_EXECUTION_ERROR', 'SCRAPER_INVALID_JSON', # Scraper failures
                    'RAW_DATA_DATE_PARSE_ERROR', 'RAW_DATA_VALUE_PARSE_ERROR', # Data parsing errors
                    'SCRAPER_SCRIPT_NOT_FOUND', # Scraper script issues
                    'PIPELINE_BLOCKED_ZONE_INACTIVE', # Pipeline blocked due to inactive zone
                    'SCRAPER_MANUAL_EXECUTION_STARTED', 'SCRAPER_MANUAL_EXECUTION_FAILED', # Manual scraper execution
                ]) |
                # Technical management logs (their direct domain)
                Q(action__in=[
                    'ZONE_CREATED', 'ZONE_DELETED', 'ZONE_STATUS_TOGGLED', 'ZONE_PROPERTIES_UPDATED',
                    'SOURCE_CONFIGURED', 'SOURCE_MODIFIED', 'SOURCE_DELETED',
                    'SCHEDULE_CREATED', 'SCHEDULE_MODIFIED', 'SCHEDULE_DELETED', 'SCHEDULE_STATUS_SYNCHRONIZED_WITH_ZONE',
                    'ALIAS_CREATED', 'ALIAS_MODIFIED', 'ALIAS_DELETED', 'ALIAS_MANAGEMENT_FAILED', # Their alias clicks
                    # User management they might perform/monitor
                    'ADMIN_CREATED', 'CONSUMER_CREATED', 'USER_MODIFIED', 'USER_DELETED', 'USER_STATUS_TOGGLED',
                    'USER_IMPERSONATED', 'USER_REVERTED_IMPERSONATION', # All impersonation attempts
                    'UNAUTHORIZED_ACCESS_ATTEMPT', 'WEB_LOGIN_SUCCESS', 'WEB_LOGIN_FAILED', # General system security
                ])
            ).distinct()

            # Exclude specific info-level "spam" logs that are not directly actionable for AT,
            # unless their level is warning/error/critical.
            logs_queryset = logs_queryset.exclude(
                Q(action__in=['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY', 'PIPELINE_NO_RAW_DATA', 'PIPELINE_NO_DATA_FOR_DATE']) &
                ~Q(level__in=['error', 'critical', 'warning']) # DO NOT exclude if it's an error/warning
            )
            
            # Exclude SuperAdmin-only actions unless Admin Tech is the actor/impersonator
            logs_queryset = logs_queryset.exclude(
                Q(action__in=[
                    'SUPERADMIN_MODIFICATION_ATTEMPT', 'SUPERADMIN_DELETION_FAILED', 'SUPERADMIN_DELETION_ATTEMPT_FAILED',
                    'SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                ]) &
                ~Q(actor=admin_tech_user) &
                ~Q(impersonator=admin_tech_user)
            )

        elif user_role == 'ADMIN_ZONE':
            admin_zone_user = current_logged_in_user_obj
            user_managed_zone = admin_zone_user.zone

            if not user_managed_zone:
                # If Admin Zone user is not assigned to a zone, they only see their own actions
                logs_queryset = logs_queryset.filter(
                    Q(actor=admin_zone_user) |
                    Q(impersonator=admin_zone_user) |
                    Q(target_user=admin_zone_user)
                ).distinct()
            else:
                logs_queryset = logs_queryset.filter(
                    # Always see their own direct actions
                    Q(actor=admin_zone_user) |
                    Q(impersonator=admin_zone_user) |
                    Q(target_user=admin_zone_user) |
                    # Pipeline execution results (success/failure) for THEIR zone's source only
                    Q(zone=user_managed_zone, action__in=[
                        'PIPELINE_EXECUTION_SUCCESS', 'PIPELINE_EXECUTION_COMPLETED',
                        # Explicitly include critical/error/warning logs related to pipeline for THEIR zone
                        'PIPELINE_ERROR', 'PIPELINE_CALCULATION_ERROR', 'PIPELINE_UNEXPECTED_ERROR',
                        'SCRAPER_TIMEOUT', 'SCRAPER_EXECUTION_ERROR', 'SCRAPER_INVALID_JSON',
                        'RAW_DATA_DATE_PARSE_ERROR', 'RAW_DATA_VALUE_PARSE_ERROR',
                        'PIPELINE_BLOCKED_ZONE_INACTIVE', # Relevant if their zone causes blockage
                    ]) |
                    # Their primary responsibility: Currency Activation
                    Q(action='CURRENCY_ACTIVATION_TOGGLED', zone=user_managed_zone) | # Their explicit clicks
                    # New Mappings for their zone (via Admin Tech's action)
                    Q(action__in=['ALIAS_CREATED', 'ALIAS_MODIFIED'], zone=user_managed_zone) |
                    # API access logs for consumers in their zone
                    Q(action__in=['API_LOGIN_SUCCESS', 'API_LOGIN_FAILED'], target_user__zone=user_managed_zone)
                ).distinct()

                # Explicitly exclude info-level "spam" logs for Admin Zone
                logs_queryset = logs_queryset.exclude(
                    Q(action__in=['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY', 'PIPELINE_NO_RAW_DATA', 'PIPELINE_NO_DATA_FOR_DATE']) &
                    ~Q(level__in=['error', 'critical', 'warning']) & # Do NOT exclude if it's an error/warning
                    Q(zone=user_managed_zone) # Only apply these exclusions if the log is for their zone
                )

                # Exclude general admin/superadmin actions not related to their zone or themselves
                logs_queryset = logs_queryset.exclude(
                    Q(action__in=[
                        'SUPERADMIN_MODIFICATION_ATTEMPT', 'SUPERADMIN_DELETION_FAILED', 'SUPERADMIN_DELETION_ATTEMPT_FAILED',
                        'SUPERADMIN_STATUS_TOGGLE_ATTEMPT',
                        'ADMIN_CREATED', 'CONSUMER_CREATED', 'USER_DELETED', 'USER_MODIFIED', 'USER_STATUS_TOGGLED',
                        'SCHEDULE_CREATED', 'SCHEDULE_MODIFIED', 'SCHEDULE_DELETED', 'SCHEDULE_STATUS_SYNCHRONIZED_WITH_ZONE',
                        'SOURCE_CONFIGURED', 'SOURCE_MODIFIED', 'SOURCE_DELETED',
                        'ALIAS_DELETED', 'ALIAS_MANAGEMENT_FAILED', # Deletion/failure of aliases might be less critical for AZ
                        'SCRAPER_MANUAL_EXECUTION_STARTED', 'SCRAPER_MANUAL_EXECUTION_FAILED',
                        'USER_IMPERSONATED', 'USER_REVERTED_IMPERSONATION',
                        'UNAUTHORIZED_ACCESS_ATTEMPT', 'WEB_LOGIN_SUCCESS', 'WEB_LOGIN_FAILED', # General security logs not specific to their consumers
                    ]) &
                    ~Q(actor=admin_zone_user) & ~Q(impersonator=admin_zone_user) & ~Q(target_user=admin_zone_user) & # Not performed by themselves
                    ~Q(zone=user_managed_zone) # Not related to their zone
                )

        # Pagination (remains common for all roles)
        page = request.GET.get('page', 1)
        paginator = Paginator(logs_queryset, 20)
        try:
            logs = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            logs = paginator.page(paginator.num_pages)

        # Prepare base query string for pagination links (excluding 'page' param)
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

        # Render the appropriate partial or full page based on HX-Request header
        if request.headers.get('HX-Request'):
            return render(request, "common/_audit_log_table.html", context)
            
        return render(request, "common/audit_log.html", context)