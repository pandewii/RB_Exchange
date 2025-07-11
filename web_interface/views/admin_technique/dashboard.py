# web_interface/views/admin_technique/dashboard.py

from django.shortcuts import render, redirect
from .shared import get_zones_with_status

def dashboard_view(request):
    # Sécurité : on vérifie que l'utilisateur est bien un AdminTechnique
    if request.session.get("role") != "ADMIN_TECH":
        return redirect("login")

    # On utilise notre nouvelle fonction pour récupérer les données enrichies
    zones_data = get_zones_with_status()

    context = {
        "zones_with_status": zones_data
    }
    
    return render(request, "admin_technique/dashboard.html", context)