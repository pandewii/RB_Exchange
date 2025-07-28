# web_interface/views/admin_zone/dashboard.py

from django.shortcuts import render, redirect, get_object_or_404
from core.models import Devise, ActivatedCurrency, ZoneMonetaire, ScrapedCurrencyRaw, DeviseAlias # NOUVEL AJOUT: ScrapedCurrencyRaw, DeviseAlias
from users.models import CustomUser
from logs.models import UINotification
from django.http import HttpResponse

def dashboard_view(request):
    user_role = request.session.get("role")
    user_id = request.session.get("user_id")

    if user_role != "ADMIN_ZONE":
        return redirect("login")

    admin_zone_user = get_object_or_404(CustomUser, pk=user_id)
    if not admin_zone_user.zone:
        return render(request, "admin_zone/dashboard.html", {
            "zone": None,
            "error_message": "Votre compte Admin Zone n'est pas associé à une zone monétaire.",
            "all_devises": [],
            "active_codes": set(),
            "unread_notifications": []
        })

    zone = admin_zone_user.zone
    
    # MODIFICATION MAJEURE ICI : Récupérer uniquement les devises pertinentes pour la zone
    # 1. Trouver la source de la zone
    source = None
    if hasattr(zone, 'source'):
        source = zone.source

    relevant_devises = Devise.objects.none() # Queryset vide par défaut
    active_codes = set() # Set des devises activées
    
    if source:
        # Récupérer les codes ISO bruts distincts de ScrapedCurrencyRaw pour cette source
        scraped_codes_for_zone = ScrapedCurrencyRaw.objects.filter(
            source=source
        ).values_list('code_iso_brut', flat=True).distinct()

        # Récupérer tous les alias qui pointent vers des devises officielles
        # et dont le nom brut (alias) correspond à un code scrappé
        mapped_official_devise_ids = DeviseAlias.objects.filter(
            alias__in=[code.upper() for code in scraped_codes_for_zone if code] # Assurer la casse
        ).values_list('devise_officielle__code', flat=True).distinct()

        # Récupérer les objets Devise officiels qui sont mappés
        relevant_devises = Devise.objects.filter(code__in=mapped_official_devise_ids).order_by('code')

        # Récupérer les codes des devises déjà activées pour cette zone
        activated_devises = ActivatedCurrency.objects.filter(zone=zone, is_active=True).values_list('devise__code', flat=True)
        active_codes = set(activated_devises)
    
    # Si pas de source, ou aucune devise mappée, all_devises reste un queryset vide ou celles qui sont juste activées
    if not source and ActivatedCurrency.objects.filter(zone=zone, is_active=True).exists():
        relevant_devises = Devise.objects.filter(code__in=active_codes).order_by('code')


    unread_notifications = []
    if request.user.is_authenticated:
        unread_notifications = UINotification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-timestamp')[:10]

    context = {
        "zone": zone,
        "all_devises": relevant_devises, # MODIFIÉ
        "active_codes": active_codes,
        "unread_notifications": unread_notifications,
    }
    return render(request, "admin_zone/dashboard.html", context)
