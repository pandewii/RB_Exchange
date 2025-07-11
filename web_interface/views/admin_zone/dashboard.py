# web_interface/views/admin_zone/dashboard.py

from django.shortcuts import render, redirect
from .shared import get_dashboard_context

def dashboard_view(request):
    if request.session.get("role") != "ADMIN_ZONE":
        return redirect("login")
    
    user_id = request.session.get('user_id')
    context = get_dashboard_context(user_id)
    
    return render(request, "admin_zone/dashboard.html", context)