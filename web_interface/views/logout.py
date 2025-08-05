from django.shortcuts import redirect
from django.contrib.auth import logout as auth_logout
from django.views.decorators.http import require_http_methods
from logs.utils import log_action 
from users.models import CustomUser 

@require_http_methods(["GET", "POST"])
def logout_view(request):
    user_id_for_log = None
    user_email_for_log = None
    user_role_for_log = None
    zone_obj_for_log = None

    # Capture user details BEFORE logging out, as request.user will become AnonymousUser
    if request.user.is_authenticated:
        user_id_for_log = request.user.pk
        user_email_for_log = request.user.email
        user_role_for_log = request.user.role
        zone_obj_for_log = request.user.zone
    
    auth_logout(request) # This clears the session and logs the user out

    log_action(
        actor_id=user_id_for_log,
        action='WEB_LOGOUT_SUCCESS',
        details=f"Déconnexion web réussie pour l'utilisateur {user_email_for_log if user_email_for_log else 'Inconnu'} (ID: {user_id_for_log if user_id_for_log else 'N/A'}, Rôle: {user_role_for_log if user_role_for_log else 'N/A'}).",
        level='info',
        zone_obj=zone_obj_for_log,
        source_obj=None
    )

    return redirect('login')