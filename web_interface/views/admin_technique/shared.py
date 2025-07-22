# web_interface/views/admin_technique/shared.py

from core.models import Source, ScrapedCurrencyRaw, DeviseAlias, ZoneMonetaire
from users.models import CustomUser # Importation nécessaire pour accéder aux utilisateurs

def get_daily_photocopy(source: Source):
    """
    Fonction utilitaire qui prend une Source et retourne la liste
    des devises brutes de la dernière exécution du scraper,
    ainsi que le dictionnaire des alias.
    """
    photocopy_of_the_day = []
    aliases_dict = {}

    # 1. Trouver la date de la dernière publication pour cette source
    latest_raw_data = ScrapedCurrencyRaw.objects.filter(source=source).order_by('-date_publication_brut', '-id').first()
    
    if latest_raw_data:
        latest_publication_date = latest_raw_data.date_publication_brut
        
        # 2. Récupérer uniquement les enregistrements de cette dernière date
        raw_currencies_for_today = ScrapedCurrencyRaw.objects.filter(
            source=source,
            date_publication_brut=latest_publication_date
        )
        
        # 3. Récupérer tous les alias connus du système
        aliases = DeviseAlias.objects.select_related('devise_officielle').all()
        aliases_dict = {alias.alias: alias.devise_officielle for alias in aliases}
        
        # 4. Trier la "photocopie" du jour pour mettre les devises non mappées en premier
        photocopy_of_the_day = sorted(
            raw_currencies_for_today,
            key=lambda x: (x.nom_devise_brut.upper() not in aliases_dict) and (x.code_iso_brut.upper() not in aliases_dict),
            reverse=True
        )

    return photocopy_of_the_day, aliases_dict

# MODIFICATION : La fonction get_zones_with_status doit maintenant prendre 'request'
def get_zones_with_status(request):
    """
    Récupère toutes les zones et les enrichit avec
    le statut de mapping et de planification.
    MODIFICATION : Ajoute l'utilisateur AdminZone pour la zone et le rôle de l'utilisateur actuel.
    """
    zones = ZoneMonetaire.objects.prefetch_related('source', 'source__periodic_task', 'users').all()
    zones_with_status = []


    for zone in zones:
        unmapped_count = -1  # -1 signifie "pas de source"
        is_scheduled = False
        admin_zone_user = None # Initialiser à None

        if hasattr(zone, 'source') and zone.source:
            photocopy, aliases_dict = get_daily_photocopy(zone.source)
            
            # Calcul du statut de mapping
            if photocopy:
                unmapped_count = sum(1 for c in photocopy if (c.nom_devise_brut.upper() not in aliases_dict) and (c.code_iso_brut.upper() not in aliases_dict))
            else:
                unmapped_count = 0 # Pas de devises à mapper, donc 0 non mappées

            # Calcul du statut de planification
            if zone.source.periodic_task and zone.source.periodic_task.enabled:
                is_scheduled = True
        
        # MODIFICATION : Récupérer le premier AdminZone actif pour cette zone
        # Ceci est utilisé pour le bouton d'impersonation dans le template.
        admin_zone_user = CustomUser.objects.filter(
            zone=zone,
            role='ADMIN_ZONE',
            is_active=True
        ).first()

        zones_with_status.append({
            'zone': zone,
            'unmapped_count': unmapped_count,
            'is_scheduled': is_scheduled,
            'admin_zone_user': admin_zone_user, # AJOUT : passer l'objet AdminZone trouvé
        })
    
    # MODIFICATION : Retourner le rôle de l'utilisateur actuel en plus des données des zones
    return zones_with_status, request.session.get('role')