# web_interface/views/admin_technique/shared.py

from core.models import Source, ScrapedCurrencyRaw, DeviseAlias, ZoneMonetaire

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
            # --- DÉBUT DE LA CORRECTION ---
            # On vérifie si le nom OU le code ISO est mappé pour déterminer le statut.
            key=lambda x: (x.nom_devise_brut not in aliases_dict) and (x.code_iso_brut not in aliases_dict),
            # --- FIN DE LA CORRECTION ---
            reverse=True
        )

    return photocopy_of_the_day, aliases_dict
def get_zones_with_status():
    """
    NOUVELLE FONCTION : Récupère toutes les zones et les enrichit avec
    le statut de mapping et de planification.
    """
    zones = ZoneMonetaire.objects.prefetch_related('source', 'source__periodic_task').all()
    zones_with_status = []

    for zone in zones:
        unmapped_count = -1  # -1 signifie "pas de source"
        is_scheduled = False

        if hasattr(zone, 'source') and zone.source:
            photocopy, aliases_dict = get_daily_photocopy(zone.source)
            
            # Calcul du statut de mapping
            if photocopy:
                unmapped_count = sum(1 for c in photocopy if (c.nom_devise_brut not in aliases_dict) and (c.code_iso_brut not in aliases_dict))
            else:
                unmapped_count = 0 # Pas de devises à mapper, donc 0 non mappées

            # Calcul du statut de planification
            if zone.source.periodic_task and zone.source.periodic_task.enabled:
                is_scheduled = True

        zones_with_status.append({
            'zone': zone,
            'unmapped_count': unmapped_count,
            'is_scheduled': is_scheduled
        })
    
    return zones_with_status