# web_interface/views/admin_technique/shared.py

from core.models import Source, ScrapedCurrencyRaw, DeviseAlias, ZoneMonetaire
from users.models import CustomUser 

def get_daily_photocopy(source: Source):
    """
    Fonction utilitaire qui prend une Source et retourne la liste
    des devises brutes de la dernière exécution du scraper,
    ainsi que le dictionnaire des alias.
    """
    photocopy_of_the_day = []
    aliases_dict = {}

    latest_raw_data = ScrapedCurrencyRaw.objects.filter(source=source).order_by('-date_publication_brut', '-id').first()
    
    if latest_raw_data:
        latest_publication_date = latest_raw_data.date_publication_brut
        
        raw_currencies_for_today = ScrapedCurrencyRaw.objects.filter(
            source=source,
            date_publication_brut=latest_publication_date
        )
        
        aliases = DeviseAlias.objects.select_related('devise_officielle').all()
        aliases_dict = {alias.alias: alias.devise_officielle for alias in aliases}
        
        photocopy_of_the_day = sorted(
            raw_currencies_for_today,
            key=lambda x: (x.nom_devise_brut.upper() not in aliases_dict) and (x.code_iso_brut.upper() not in aliases_dict),
            reverse=True
        )

    return photocopy_of_the_day, aliases_dict

def get_zones_with_status(request):
    """
    Récupère toutes les zones et les enrichit avec
    le statut de mapping et de planification.
    MODIFICATION : Ajoute l'utilisateur AdminZone pour la zone et le rôle de l'utilisateur actuel.
    """
    zones = ZoneMonetaire.objects.prefetch_related('source', 'source__periodic_task', 'users').all()
    zones_with_status = []

    # Get current user's role directly from request.user
    current_user_role_from_request = request.user.role if request.user.is_authenticated else None

    for zone in zones:
        unmapped_count = -1  # -1 signifie "pas de source"
        is_scheduled = False
        admin_zone_user = None # Initialiser à None

        if hasattr(zone, 'source') and zone.source:
            photocopy, aliases_dict = get_daily_photocopy(zone.source)
            
            if photocopy:
                unmapped_count = sum(1 for c in photocopy if (c.nom_devise_brut.upper() not in aliases_dict) and (c.code_iso_brut.upper() not in aliases_dict))
            else:
                unmapped_count = 0 

            if zone.source.periodic_task and zone.source.periodic_task.enabled:
                is_scheduled = True
        
        # Use .filter().first() to get the AdminZone user safely
        admin_zone_user = CustomUser.objects.filter(
            zone=zone,
            role='ADMIN_ZONE',
            is_active=True
        ).first()

        zones_with_status.append({
            'zone': zone,
            'unmapped_count': unmapped_count,
            'is_scheduled': is_scheduled,
            'admin_zone_user': admin_zone_user,
        })
    
    # Return the role from request.user, not session.
    return zones_with_status, current_user_role_from_request