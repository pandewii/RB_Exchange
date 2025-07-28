from django.shortcuts import redirect

def logout_view(request):
    request.session.flush()
    # On redirige directement et simplement vers la page de connexion.
    return redirect("login")
