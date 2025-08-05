# authentication/views/impersonate_helper.py

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.views.decorators.http import require_http_methods
from users.models import CustomUser
from logs.utils import log_action
from django.urls import reverse
from django.contrib.auth import logout as auth_logout_internal # Added: Import logout

@require_http_methods(["GET"])
def impersonate_login_helper(request):
    # This view performs the actual Django login for the target user (impersonated or reverted to)
    # It takes the target_user_id from a temporary session variable.

    if not request.user.is_authenticated:
        # If the user is somehow not authenticated when reaching this helper, redirect to login
        # This can happen if the session was cleared or expired.
        return redirect('login')

    target_user_id = request.session.get('impersonate_target_user_id')
    impersonation_stack = request.session.get('impersonation_stack', []) # Preserve stack

    if not target_user_id:
        # Critical error: helper called without a target user ID
        log_action(
            actor_id=request.user.pk,
            action='IMPERSONATE_HELPER_FAILED',
            details="Impersonation helper called without target_user_id in session.",
            level='critical'
        )
        # Clear any partial impersonation state and redirect to login
        if 'impersonate_target_user_id' in request.session:
            del request.session['impersonate_target_user_id']
        request.session.flush() # Clear invalid session state
        return redirect('login')

    try:
        target_user = get_object_or_404(CustomUser, pk=target_user_id)
    except CustomUser.DoesNotExist:
        log_action(
            actor_id=request.user.pk,
            action='IMPERSONATE_HELPER_FAILED',
            details=f"Impersonation helper: Target user with ID {target_user_id} not found in DB.",
            level='critical'
        )
        # Clear any partial impersonation state and redirect to login
        if 'impersonate_target_user_id' in request.session:
            del request.session['impersonate_target_user_id']
        request.session.flush() # Clear invalid session state
        return redirect('login')

    # Explicitly clear the current Django authentication state
    # This ensures no remnants of the *previous* Django authenticated user (even if anonymous) remain.
    auth_logout_internal(request)

    # Perform the standard Django login for the target user
    auth_login(request, target_user)

    # Restore the custom session variables (these were already set in impersonate/revert views, but for safety)
    request.session['user_id'] = target_user.pk
    request.session['role'] = target_user.role
    request.session['email'] = target_user.email
    request.session['impersonation_stack'] = impersonation_stack # Restore the stack
    request.session.modified = True # Ensure session is saved

    # Clean up the temporary session variable
    if 'impersonate_target_user_id' in request.session:
        del request.session['impersonate_target_user_id']

    # Redirect to the appropriate dashboard based on the target user's role
    dashboard_url = ''
    if target_user.role == 'SUPERADMIN':
        dashboard_url = reverse('superadmin_dashboard')
    elif target_user.role == 'ADMIN_TECH':
        dashboard_url = reverse('admin_technique_dashboard')
    elif target_user.role == 'ADMIN_ZONE':
        dashboard_url = reverse('admin_zone_dashboard')
    elif target_user.role == 'WS_USER':
        # WS_USERs don't have a dedicated web dashboard, redirect to index (or login if preferred for them)
        dashboard_url = reverse('index')
    else:
        dashboard_url = reverse('index') # Fallback for unexpected roles

    return redirect(dashboard_url)