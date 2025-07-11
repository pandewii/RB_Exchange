# web_interface/views/login.py

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.contrib.auth import authenticate
from users.models import CustomUser
from django.views.decorators.cache import never_cache

def index_view(request):
    """
    Vue d'accueil qui agit comme un aiguilleur.
    """
    if request.session.get('user_id'):
        role = request.session.get('role')
        if role == 'SUPERADMIN':
            return redirect(reverse('superadmin_dashboard'))
        elif role == 'ADMIN_TECH':
            return redirect(reverse('admin_technique_dashboard'))
        # --- DÉBUT DE LA CORRECTION ---
        elif role == 'ADMIN_ZONE':
            # On ajoute la redirection pour l'Admin Zone
            return redirect(reverse('admin_zone_dashboard'))
        # --- FIN DE LA CORRECTION ---
        else:
            # Pour tous les autres cas (ou rôle inconnu), on déconnecte et redirige au login
            request.session.flush()
            return redirect(reverse('login'))
            
    return redirect(reverse('login'))

@never_cache
def login_view(request):
    """
    Gère le processus de connexion de l'utilisateur.
    """
    # La garde d'authentification au début est correcte et ne change pas
    if request.session.get('user_id'):
        return redirect(reverse('index'))

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        
        try:
            user = CustomUser.objects.get(email__iexact=email)
            if user.check_password(password):
                if user.is_active:
                    request.session.flush()
                    request.session['user_id'] = user.pk
                    request.session['role'] = user.role
                    request.session['email'] = user.email
                    request.session.set_expiry(0)

                    redirect_url = reverse('index')
                    
                    response = HttpResponse(status=204)
                    response['HX-Redirect'] = redirect_url
                    return response
                else:
                    error_message = "<p>Ce compte est désactivé. Veuillez contacter un administrateur.</p>"
            else:
                error_message = "<p>Email ou mot de passe incorrect.</p>"
        except CustomUser.DoesNotExist:
            error_message = "<p>Email ou mot de passe incorrect.</p>"

        response = HttpResponse(error_message)
        response['HX-Retarget'] = '#form-error-message'
        response['HX-Reswap'] = 'innerHTML'
        return response

    return render(request, "login.html")