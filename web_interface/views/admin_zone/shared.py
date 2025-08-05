# web_interface/views/admin_zone/shared.py

from users.models import CustomUser
from core.models import Devise, ActivatedCurrency, Source, ScrapedCurrencyRaw, DeviseAlias
from django.db.models import Q # Add Q import for combined filtering in case needed elsewhere.

def get_dashboard_context(user_id):
    """
    Fonction partagée qui prépare le contexte pour le tableau de bord de l'Admin Zone.
    La liste des devises mappées est désormais filtrée pour n'inclure que celles
    qui sont présentes dans les dernières données brutes de la source de la zone.
    """
    # Use select_related('zone__source') to efficiently fetch the zone and its related source
    user = CustomUser.objects.select_related('zone', 'zone__source').get(pk=user_id)
    
    if not user.zone:
        return {"error": "Vous n'êtes assigné à aucune zone."}

    # Accéder à la source via la relation inverse OneToOneField
    # If a ZoneMonetaire object has a Source, it can be accessed as zone.source
    source = user.zone.source if hasattr(user.zone, 'source') else None
    
    all_mapped_devises_to_display = Devise.objects.none()

    if source: # Only proceed if a source is found for the zone
        latest_raw_data_entry = ScrapedCurrencyRaw.objects.filter(
            source=source,
            date_publication_brut__isnull=False
        ).order_by('-date_publication_brut', '-date_scraping').first()

        if latest_raw_data_entry:
            latest_date = latest_raw_data_entry.date_publication_brut
            
            # Get all relevant raw identifiers (nom_devise_brut and code_iso_brut) for the latest date
            raw_identifiers = set()
            for raw_currency in ScrapedCurrencyRaw.objects.filter(
                source=source,
                date_publication_brut=latest_date
            ):
                if raw_currency.nom_devise_brut:
                    raw_identifiers.add(raw_currency.nom_devise_brut.upper())
                if raw_currency.code_iso_brut:
                    raw_identifiers.add(raw_currency.code_iso_brut.upper())
            
            if raw_identifiers:
                # Find all DeviseAlias entries where the 'alias' matches one of our raw_identifiers
                # And then get the distinct official Devise objects linked by these aliases
                all_mapped_devises_to_display = Devise.objects.filter(
                    aliases__alias__in=list(raw_identifiers)
                ).distinct().order_by('nom')
        
    activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=user.zone, is_active=True)
    active_codes = set(d.devise.code for d in activated_devises_for_zone)

    context = {
        'zone': user.zone,
        'all_mapped_devises': all_mapped_devises_to_display,
        'active_codes': active_codes
    }
    
    return context