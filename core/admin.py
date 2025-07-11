from django.contrib import admin
from .models import (
    ZoneMonetaire, Source, Devise, DeviseAlias,
    ScrapedCurrencyRaw, ActivatedCurrency, ExchangeRate
)

# Enregistrement des modèles dans l'interface d'administration

# Admin pour ZoneMonetaire
@admin.register(ZoneMonetaire)
class ZoneMonetaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('nom',)

# Admin pour Source
@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('zone', 'nom', 'url_source', 'scraper_filename', 'periodic_task', 'date_creation')
    list_filter = ('scraper_filename', 'date_creation')
    search_fields = ('nom', 'url_source', 'zone__nom')
    raw_id_fields = ('periodic_task',) # Pour un sélecteur plus propre si beaucoup de tâches

# Admin pour Devise
@admin.register(Devise)
class DeviseAdmin(admin.ModelAdmin):
    list_display = ('code', 'nom')
    search_fields = ('code', 'nom')

# Admin pour DeviseAlias
@admin.register(DeviseAlias)
class DeviseAliasAdmin(admin.ModelAdmin):
    list_display = ('alias', 'devise_officielle')
    list_filter = ('devise_officielle',)
    search_fields = ('alias', 'devise_officielle__code', 'devise_officielle__nom')

# Admin pour ScrapedCurrencyRaw
@admin.register(ScrapedCurrencyRaw)
class ScrapedCurrencyRawAdmin(admin.ModelAdmin):
    list_display = (
        'source', 'date_publication_brut', 'nom_devise_brut', 'code_iso_brut',
        'valeur_brute', 'multiplicateur_brut', 'date_scraping'
    )
    list_filter = ('source', 'date_publication_brut', 'date_scraping')
    search_fields = ('source__nom', 'nom_devise_brut', 'code_iso_brut')
    readonly_fields = ('date_scraping',) # Le scraping est automatique

# Admin pour ActivatedCurrency
@admin.register(ActivatedCurrency)
class ActivatedCurrencyAdmin(admin.ModelAdmin):
    list_display = ('zone', 'devise', 'is_active')
    list_filter = ('zone', 'devise', 'is_active')
    search_fields = ('zone__nom', 'devise__code', 'devise__nom')

# Admin pour ExchangeRate
@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = (
        'devise', 'zone', 'date_publication', 
        'taux_source', 'multiplicateur_source', 'taux_normalise', # CORRECTION: Nouveaux champs
        'is_latest', 'date_creation_interne'
    )
    list_filter = ('zone', 'devise', 'date_publication', 'is_latest')
    search_fields = ('zone__nom', 'devise__code', 'devise__nom')
    readonly_fields = ('date_creation_interne',) # Le taux final est créé automatiquement
    # Pour un graphique ou une vue plus complexe, on pourrait utiliser des filtres personnalisés ou un change_list_template