# web_interface/views/admin_zone/shared.py

from users.models import CustomUser
from core.models import Devise, ActivatedCurrency, Source, ScrapedCurrencyRaw # Importez Source et ScrapedCurrencyRaw
from django.db.models import Max # Importez Max pour trouver la date la plus récente

def get_dashboard_context(user_id):
    """
    Fonction partagée qui prépare le contexte pour le tableau de bord de l'Admin Zone.
    La liste des devises mappées est désormais filtrée pour n'inclure que celles
    qui sont présentes dans les dernières données brutes de la source de la zone.
    """
    user = CustomUser.objects.select_related('zone').get(pk=user_id)
    
    if not user.zone:
        return {"error": "Vous n'êtes assigné à aucune zone."}

    # Récupérer la source associée à la zone de l'utilisateur
    source = Source.objects.filter(zone=user.zone).first()
    
    # Initialiser la liste des devises mappées à afficher
    all_mapped_devises_to_display = Devise.objects.none() # Commencer avec un queryset vide

    if source:
        # Trouver la date de publication la plus récente pour cette source
        latest_raw_data_entry = ScrapedCurrencyRaw.objects.filter(
            source=source,
            date_publication_brut__isnull=False
        ).order_by('-date_publication_brut', '-date_scraping').first()

        if latest_raw_data_entry:
            latest_date = latest_raw_data_entry.date_publication_brut
            
            # Récupérer les codes ISO bruts uniques des devises de la dernière "photocopie"
            # Assurez-vous que code_iso_brut n'est pas vide et le convertissez en majuscules pour la correspondance
            latest_raw_iso_codes = ScrapedCurrencyRaw.objects.filter(
                source=source,
                date_publication_brut=latest_date
            ).exclude(code_iso_brut__exact='').values_list('code_iso_brut', flat=True)
            
            # Convertir tous les codes en majuscules pour la recherche
            latest_raw_iso_codes_upper = [code.upper() for code in latest_raw_iso_codes]

            # Filtrer les devises officielles:
            # 1. Elles doivent avoir un alias (être mappées)
            # 2. Leur code doit correspondre à un code ISO brut trouvé dans les dernières données scrapées
            all_mapped_devises_to_display = Devise.objects.filter(
                aliases__isnull=False, # S'assurer qu'il y a un alias
                code__in=latest_raw_iso_codes_upper # Le code officiel correspond à un code brut récent
            ).distinct().order_by('nom')
        
    # On récupère les devises qui sont spécifiquement activées pour la zone de cet utilisateur
    activated_devises_for_zone = ActivatedCurrency.objects.filter(zone=user.zone, is_active=True)
    
    # On crée un set des codes de devises actives pour une recherche rapide dans le template
    active_codes = set(d.devise.code for d in activated_devises_for_zone)

    context = {
        'zone': user.zone,
        'all_mapped_devises': all_mapped_devises_to_display, # Utilisez la liste filtrée
        'active_codes': active_codes
    }
    
    return context
