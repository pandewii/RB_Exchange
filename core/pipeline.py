# core/pipeline.py

from .models import Source, DeviseAlias, ActivatedCurrency, ExchangeRate, Devise
from datetime import datetime
from decimal import Decimal
import sys
from logs.utils import log_action # NOUVEAU: Importation de log_action

def process_and_inject_rates(source_id: int):
    """
    Le cœur du pipeline. Cette fonction prend les données brutes les plus récentes
    pour une source, les filtre, les calcule et les les injecte dans la table finale ExchangeRate.
    """
    try:
        source = Source.objects.select_related('zone').get(pk=source_id)
    except Source.DoesNotExist:
        log_action(
            actor_id=None, # Action système
            action='PIPELINE_ERROR',
            details=f"Erreur Pipeline: La source avec l'ID {source_id} n'a pas été trouvée lors du traitement.",
            level='critical',
            source_id=source_id # Passer l'ID de la source même si elle n'existe pas, si possible
        )
        return "Erreur : Source non trouvée."

    latest_raw_data_entry = source.raw_data.filter(date_publication_brut__isnull=False).order_by('-date_publication_brut', '-date_scraping').first()
    if not latest_raw_data_entry:
        log_action(
            actor_id=None, # Action système
            action='PIPELINE_NO_RAW_DATA',
            details=f"Aucune donnée brute récente à traiter pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
            level='warning',
            source_id=source_id,
            zone_id=source.zone.pk
        )
        return "Aucune donnée brute récente à traiter."
    
    latest_date = latest_raw_data_entry.date_publication_brut
    raw_currencies_for_today = source.raw_data.filter(date_publication_brut=latest_date)

    if not raw_currencies_for_today.exists():
        log_action(
            actor_id=None, # Action système
            action='PIPELINE_NO_DATA_FOR_DATE',
            details=f"Aucune donnée brute pour la date '{latest_date}' à traiter pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
            level='warning',
            source_id=source_id,
            zone_id=source.zone.pk
        )
        return f"Aucune donnée brute pour la date {latest_date} à traiter pour la source {source.nom}."

    # Pré-charger toutes les devises officielles pour une recherche rapide par code ISO
    official_devises_by_code = {devise.code: devise for devise in Devise.objects.all()}

    aliases_dict = {
        alias.alias: alias.devise_officielle 
        for alias in DeviseAlias.objects.select_related('devise_officielle').all()
    }
    
    active_codes_for_zone = set(
        ac.devise.code 
        for ac in ActivatedCurrency.objects.filter(zone=source.zone, is_active=True)
    )

    injected_count = 0
    skipped_identical_count = 0

    for raw_currency in raw_currencies_for_today:
        # Tente de trouver la devise officielle via le nom brut ou le code ISO brut
        # La logique d'auto-mapping n'est pas présente dans cette version
        official_devise = aliases_dict.get(raw_currency.nom_devise_brut) or \
                          aliases_dict.get(raw_currency.code_iso_brut)
        
        if not official_devise:
            log_action(
                actor_id=None, # Action système
                action='PIPELINE_UNMAPPED_CURRENCY',
                details=f"Devise brute non mappée '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Code ISO: {raw_currency.code_iso_brut}) pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
                level='info', # Info, car c'est attendu et géré par l'admin technique
                source_id=source_id,
                zone_id=source.zone.pk,
                currency_code=raw_currency.code_iso_brut
            )
            continue

        if official_devise.code not in active_codes_for_zone:
            log_action(
                actor_id=None, # Action système
                action='PIPELINE_INACTIVE_CURRENCY',
                details=f"Devise officielle '{official_devise.code}' (Nom: {official_devise.nom}) pour la source '{source.nom}' (ID: {source.pk}) n'est pas active dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
                level='info', # Info, car c'est une configuration gérée par l'admin zone
                source_id=source_id,
                zone_id=source.zone.pk,
                currency_code=official_devise.code
            )
            continue

        try:
            valeur_brute_source = raw_currency.valeur_brute
            multiplicateur_brut_source = Decimal(raw_currency.multiplicateur_brut) if raw_currency.multiplicateur_brut > 0 else Decimal('1')
            
            taux_normalise_calcule = valeur_brute_source / multiplicateur_brut_source
            taux_normalise_calcule = taux_normalise_calcule.quantize(Decimal('0.000000001'))

        except Exception as e: # Capture générique, comme avant
            log_action(
                actor_id=None, # Action système
                action='PIPELINE_CALCULATION_ERROR',
                details=f"Erreur de calcul pour '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Code ISO: {raw_currency.code_iso_brut}) dans la source '{source.nom}' (ID: {source.pk}) de la zone '{source.zone.nom}' (ID: {source.zone.pk}). Erreur: {e}",
                level='error',
                source_id=source_id,
                zone_id=source.zone.pk,
                currency_code=raw_currency.code_iso_brut
            )
            continue

        existing_rate = ExchangeRate.objects.filter(
            devise=official_devise,
            zone=source.zone,
            date_publication=latest_date
        ).first()

        if existing_rate:
            if (existing_rate.taux_source == valeur_brute_source and
                existing_rate.multiplicateur_source == raw_currency.multiplicateur_brut and
                existing_rate.taux_normalise == taux_normalise_calcule):
                
                if not existing_rate.is_latest:
                    existing_rate.is_latest = True
                    existing_rate.save(update_fields=['is_latest'])
                    injected_count += 1
                else:
                    skipped_identical_count += 1
                continue
            
            if existing_rate.is_latest:
                existing_rate.is_latest = False
                existing_rate.save(update_fields=['is_latest'])

        obj, created = ExchangeRate.objects.update_or_create(
            devise=official_devise,
            zone=source.zone,
            date_publication=latest_date,
            defaults={
                'taux_source': valeur_brute_source,
                'multiplicateur_source': raw_currency.multiplicateur_brut,
                'taux_normalise': taux_normalise_calcule,
                'is_latest': True
            }
        )
        
        injected_count += 1
    
    log_action(
        actor_id=None, # Action système
        action='PIPELINE_EXECUTION_COMPLETED',
        details=f"Pipeline terminé pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}). {injected_count} taux injectés/mis à jour. {skipped_identical_count} taux identiques ignorés.",
        level='info',
        source_id=source_id,
        zone_id=source.zone.pk
    )
    return f"Traitement terminé. {injected_count} taux injectés/mis à jour. {skipped_identical_count} taux identiques ignorés."