from django.shortcuts import render, redirect
from users.models import CustomUser
from core.models import ZoneMonetaire
from logs.models import LogEntry
from django.db.models import Q
from .shared import get_refreshed_dashboard_context # Import the shared function

def dashboard_view(request):
    # Access control: Redirect if not authenticated or role is incorrect
    if not request.user.is_authenticated or request.user.role != "SUPERADMIN":
        # log_action for unauthorized access is handled in the login/impersonation views
        # or can be added explicitly here if needed for direct URL access attempts
        return redirect("login")

    # Get filter parameters from GET request
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    zone_filter_id = request.GET.get('zone', 'all') # Renamed to avoid conflict with 'zone' model
    role_filter = request.GET.get('role_filter', 'all')

    # Get the data for admins and consumers using the shared function
    context = get_refreshed_dashboard_context(request, search_query, status_filter, zone_filter_id, role_filter)

    # Add general context for the page (all zones for dropdowns, search query, selected filters)
    context.update({
        "all_zones": ZoneMonetaire.objects.all(),
        "search_query": search_query,
        "status": status_filter,
        "selected_zone_id": zone_filter_id,
        "selected_role": role_filter,
        "current_user_role": request.user.role, # Use request.user.role directly
    })

    # Render the appropriate partial or full page based on HX-Request header
    if request.headers.get('HX-Request'):
        # For HTMX requests, render only the dynamic content part
        return render(request, "superadmin/partials/_full_dashboard_content.html", context)
    
    # For full page load, render the main dashboard template
    return render(request, "superadmin/dashboard.html", context)