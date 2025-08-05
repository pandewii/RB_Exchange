from django.shortcuts import render, redirect
from core.models.zone_monetaire import ZoneMonetaire
from users.models import CustomUser
from logs.models import LogEntry
from .shared import get_zones_with_status
from django.http import HttpResponse
from django.db.models import Q 

def dashboard_view(request):
    # Access control: Redirect if not authenticated via request.user or role is incorrect
    if not request.user.is_authenticated or request.user.role != "ADMIN_TECH":
        return redirect("login")

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter = request.GET.get('zone', 'all')

    # get_zones_with_status now correctly expects the full request object
    zones_with_status_data, current_user_role_from_shared = get_zones_with_status(request)

    filtered_zones_with_status = []
    for item in zones_with_status_data:
        if search_query and search_query.lower() not in item['zone'].nom.lower():
            continue
        if status_filter == 'active' and not item['zone'].is_active:
            continue
        if status_filter == 'inactive' and item['zone'].is_active:
            continue
        if zone_filter != 'all' and str(item['zone'].pk) != zone_filter:
             continue

        filtered_zones_with_status.append(item)

    critical_errors_logs = []
    # Use request.user.pk for actor/impersonator/target filters for current user
    if request.user.is_authenticated: 
        noisy_pipeline_actions = [
            "PIPELINE_UNMAPPED_CURRENCY", 
            "PIPELINE_INACTIVE_CURRENCY"
        ]
        
        critical_errors_logs = LogEntry.objects.filter(
            Q(level__in=['error', 'critical']) | 
            (Q(level='warning') & ~Q(action__in=noisy_pipeline_actions))
        ).filter(
            # Use request.user.pk for actor/impersonator/target filters for current user
            Q(actor=request.user) | # Use the actual user object here
            Q(impersonator=request.user) | # Use the actual user object here
            Q(action__in=[
                "SOURCE_CONFIGURATION_FAILED", "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR",
                "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START", "ZONE_DELETION_FAILED",
                "SCHEDULE_MANAGEMENT_FAILED", "UNAUTHORIZED_ACCESS_ATTEMPT", 
            ])
        ).order_by('-timestamp')[:5]

    context = {
        "zones_with_status": filtered_zones_with_status,
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter,
        "all_zones": ZoneMonetaire.objects.all(),
        "current_user_role": request.user.role, # Use request.user.role directly
        "critical_errors_logs": critical_errors_logs, 
    }

    if request.headers.get('HX-Request'):
        return render(request, "admin_technique/partials/_zones_table.html", context)
        
    return render(request, "admin_technique/dashboard.html", context)