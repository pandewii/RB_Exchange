from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.http import HttpResponse, JsonResponse # Import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from logs.utils import log_action
from users.models import CustomUser

@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        # Redirect authenticated users based on their role
        if request.user.role == "SUPERADMIN":
            return redirect("superadmin_dashboard")
        elif request.user.role == "ADMIN_TECH":
            return redirect("admin_technique_dashboard")
        elif request.user.role == "ADMIN_ZONE":
            return redirect("admin_zone_dashboard")
        # Fallback for WS_USER or other roles, or if role is not explicitly handled
        return redirect("index")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Attempt to authenticate
        user = authenticate(request, email=email, password=password)

        if user is not None:
            # NEW: Prevent WS_USER from logging in via the web interface
            if user.role == 'WS_USER':
                error_message = "Les comptes techniques ne peuvent pas se connecter via l'interface web."
                log_action(
                    actor_id=user.pk, # Log the WS_USER trying to log in
                    action='WEB_LOGIN_FAILED',
                    details=f"Tentative de connexion échouée pour WS_USER {user.email}: Accès web non autorisé.",
                    level='warning'
                )
                response = HttpResponse(f'<p>{error_message}</p>')
                response['HX-Retarget'] = '#form-error-message'
                response['HX-Reswap'] = 'innerHTML'
                response.status_code = 403 # Forbidden
                response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
                return response

            if user.is_active:
                auth_login(request, user)
                # Store core user details in session for easy access in templates/views
                # This is a redundant cache, request.user should be primary.
                request.session['user_id'] = user.pk
                request.session['role'] = user.role
                request.session['email'] = user.email
                request.session.modified = True # Ensure session is saved

                # Determine redirect URL based on role
                redirect_url = ""
                if user.role == "SUPERADMIN":
                    redirect_url = "superadmin_dashboard"
                elif user.role == "ADMIN_TECH":
                    redirect_url = "admin_technique_dashboard"
                elif user.role == "ADMIN_ZONE":
                    redirect_url = "admin_zone_dashboard"
                else: # Default for WS_USER or other roles without specific dashboard
                    redirect_url = "index"

                response = HttpResponse(status=204) # No Content
                response['HX-Redirect'] = redirect(redirect_url).url
                return response
            else:
                error_message = "Votre compte est inactif."
                log_action(
                    actor_id=None,
                    action='WEB_LOGIN_FAILED',
                    details=f"Tentative de connexion échouée pour {email}: Compte inactif.",
                    level='warning'
                )
        else:
            error_message = "Email ou mot de passe incorrect."
            log_action(
                actor_id=None,
                action='WEB_LOGIN_FAILED',
                details=f"Tentative de connexion échouée pour {email}: Email ou mot de passe incorrect.",
                level='warning'
            )
        
        # HTMX error response
        response = HttpResponse(f'<p>{error_message}</p>')
        response['HX-Retarget'] = '#form-error-message'
        response['HX-Reswap'] = 'innerHTML'
        response.status_code = 400
        response['HX-Trigger'] = '{"showError": "' + error_message + '"}'
        return response

    # GET request: render the login form
    return render(request, "login.html")

def index_view(request):
    """
    Redirects authenticated users to their respective dashboards.
    Unauthenticated users are redirected to the login page.
    """
    if request.user.is_authenticated:
        # User is authenticated, redirect based on their role
        if request.user.role == "SUPERADMIN":
            return redirect("superadmin_dashboard")
        elif request.user.role == "ADMIN_TECH":
            return redirect("admin_technique_dashboard")
        elif request.user.role == "ADMIN_ZONE":
            return redirect("admin_zone_dashboard")
        elif request.user.role == "WS_USER": # WS_USERs don't have a dedicated dashboard, redirect to index (or a generic welcome page)
            # If a WS_USER somehow gets to index authenticated, log them out or redirect to login.
            # They should have been blocked at login, but as a fallback.
            log_action(
                actor_id=request.user.pk,
                action='UNAUTHORIZED_WEB_ACCESS_ATTEMPT',
                details=f"WS_USER {request.user.email} a tenté d'accéder à l'interface web après authentification.",
                level='warning'
            )
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
            return redirect("login")
        else: # Fallback for any other unhandled roles
            log_action(
                actor_id=request.user.pk,
                action='UNHANDLED_ROLE_ACCESS',
                details=f"Utilisateur {request.user.email} avec un rôle non géré ({request.user.role}) a accédé à l'index.",
                level='warning'
            )
            # If a user has a valid session but an unrecognized role, log out and redirect to login
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
            return redirect("login")
    else:
        # User is not authenticated, redirect to login page
        return redirect("login")