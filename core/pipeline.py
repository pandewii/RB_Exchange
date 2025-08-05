# core/pipeline.py

from .models import Source, DeviseAlias, ActivatedCurrency, ExchangeRate, Devise
from datetime import datetime
from decimal import Decimal
import sys
from logs.utils import log_action
from django.db import transaction, IntegrityError # Import IntegrityError and transaction
from django.db.models import Q # Import Q for complex queries

@transaction.atomic
def process_and_inject_rates(source_id: int):
    """
    Le cœur du pipeline. Cette fonction prend les données brutes les plus récentes
    pour une source, les filtre, les calcule et les injecte dans la table finale ExchangeRate.
    Elle gère l'état 'is_latest' pour assurer qu'il n'y ait qu'un seul taux 'is_latest=True'
    par devise et par zone, et met à jour uniquement si les données changent réellement.
    """
    try:
        source = Source.objects.select_related('zone').get(pk=source_id)
    except Source.DoesNotExist:
        log_action(
            actor_id=None,
            action='PIPELINE_ERROR',
            details=f"Erreur Pipeline: La source avec l'ID {source_id} n'a pas été trouvée lors du traitement.",
            level='critical',
            source_id=source_id # Pass source_id here, as source_obj is None
        )
        return "Erreur : Source non trouvée."

    latest_raw_data_entry = source.raw_data.filter(date_publication_brut__isnull=False).order_by('-date_publication_brut', '-date_scraping').first()
    if not latest_raw_data_entry:
        log_action(
            actor_id=None,
            action='PIPELINE_NO_RAW_DATA',
            details=f"Aucune donnée brute récente à traiter pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
            level='warning',
            source_obj=source,
            zone_obj=source.zone
        )
        return "Aucune donnée brute récente à traiter."
    
    latest_date = latest_raw_data_entry.date_publication_brut
    raw_currencies_for_today = source.raw_data.filter(date_publication_brut=latest_date)

    if not raw_currencies_for_today.exists():
        log_action(
            actor_id=None,
            action='PIPELINE_NO_DATA_FOR_DATE',
            details=f"Aucune donnée brute pour la date '{latest_date}' à traiter pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
            level='warning',
            source_obj=source,
            zone_obj=source.zone
        )
        return f"Aucune donnée brute pour la date {latest_date} à traiter pour la source {source.nom}."

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
        official_devise = aliases_dict.get(raw_currency.nom_devise_brut) or \
                          aliases_dict.get(raw_currency.code_iso_brut)
        
        if not official_devise:
            log_action(
                actor_id=None,
                action='PIPELINE_UNMAPPED_CURRENCY',
                details=f"Devise brute non mappée '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Code ISO: {raw_currency.code_iso_brut}) pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
                level='info',
                source_obj=source,
                zone_obj=source.zone,
                currency_code=raw_currency.code_iso_brut
            )
            continue

        if official_devise.code not in active_codes_for_zone:
            log_action(
                actor_id=None,
                action='PIPELINE_INACTIVE_CURRENCY',
                details=f"Devise officielle '{official_devise.code}' (Nom: {official_devise.nom}) pour la source '{source.nom}' (ID: {source.pk}) n'est pas active dans la zone '{source.zone.nom}' (ID: {source.zone.pk}).",
                level='info',
                source_obj=source,
                zone_obj=source.zone,
                currency_code=official_devise.code
            )
            continue

        try:
            valeur_brute_source = raw_currency.valeur_brute
            multiplicateur_brut_source = Decimal(raw_currency.multiplicateur_brut) if raw_currency.multiplicateur_brut > 0 else Decimal('1')
            taux_normalise_calcule = valeur_brute_source / multiplicateur_brut_source
            taux_normalise_calcule = taux_normalise_calcule.quantize(Decimal('0.000000001'))

        except Exception as e:
            log_action(
                actor_id=None,
                action='PIPELINE_CALCULATION_ERROR',
                details=f"Erreur de calcul pour '{raw_currency.nom_devise_brut or raw_currency.code_iso_brut}' (Code ISO: {raw_currency.code_iso_brut}) dans la source '{source.nom}' (ID: {source.pk}) de la zone '{source.zone.nom}' (ID: {source.zone.pk}). Erreur: {e}",
                level='error',
                source_obj=source,
                zone_obj=source.zone,
                currency_code=raw_currency.code_iso_brut
            )
            continue

        try:
            # Step 1: Set is_latest=False for ALL existing rates for this devise+zone.
            # This is critical to ensure the unique_latest_rate_per_zone_devise constraint is not violated
            # when we make the current rate 'is_latest=True'.
            ExchangeRate.objects.filter(
                devise=official_devise,
                zone=source.zone
            ).update(is_latest=False)

            # Step 2: Now, create or update the rate for the specific date.
            # This record will now be the *only* one with is_latest=True for this devise+zone
            # because we just set all others to False.
            rate_obj, created = ExchangeRate.objects.update_or_create(
                devise=official_devise,
                zone=source.zone,
                date_publication=latest_date, # This is the key for uniqueness on date
                defaults={
                    'taux_source': valeur_brute_source,
                    'multiplicateur_source': raw_currency.multiplicateur_brut,
                    'taux_normalise': taux_normalise_calcule,
                    'is_latest': True # This record is now the latest
                }
            )

            if created:
                injected_count += 1
            else:
                # If 'created' is False, it means an existing record was found and updated.
                # update_or_create updates automatically if defaults differ from existing.
                # So, we just need to check if the update_or_create *actually changed* any fields
                # besides potentially 'is_latest' (which we always want true for the latest).
                
                # We compare the numerical values that were input. If they match the values
                # in the object *after* update_or_create, it means no numerical change occurred.
                if (rate_obj.taux_source == valeur_brute_source and
                    rate_obj.multiplicateur_source == raw_currency.multiplicateur_brut and
                    rate_obj.taux_normalise == taux_normalise_calcule):
                    # Values are identical to what we wanted to set, means no actual numerical change.
                    # This rate was already there with these values (and now its is_latest is True).
                    skipped_identical_count += 1
                else:
                    # Values were different and got updated. Count as injected/updated.
                    injected_count += 1
                    
        except IntegrityError as e:
            # This catch block is for any remaining IntegrityErrors,
            # which should be very rare with the above logic, unless
            # there are concurrent transactions or other unexpected data issues.
            log_action(
                actor_id=None,
                action='PIPELINE_DB_INTEGRITY_ERROR',
                details=f"Erreur d'intégrité de la base de données lors de l'injection du taux pour '{official_devise.code}' dans la zone '{source.zone.nom}'. Erreur: {e}. Output trace: {sys.exc_info()}",
                level='error',
                source_obj=source,
                zone_obj=source.zone,
                currency_code=official_devise.code
            )
            continue
        except Exception as e:
            # Catch any other unexpected errors during DB operation
            log_action(
                actor_id=None,
                action='PIPELINE_UNEXPECTED_DB_ERROR',
                details=f"Erreur inattendue lors de l'injection/mise à jour du taux pour '{official_devise.code}' dans la zone '{source.zone.nom}'. Erreur: {e}. Output trace: {sys.exc_info()}",
                level='critical',
                source_obj=source,
                zone_obj=source.zone,
                currency_code=official_devise.code
            )
            continue

    log_action(
        actor_id=None,
        action='PIPELINE_EXECUTION_COMPLETED',
        details=f"Pipeline terminé pour la source '{source.nom}' (ID: {source.pk}) dans la zone '{source.zone.nom}' (ID: {source.zone.pk}). {injected_count} taux injectés/mis à jour. {skipped_identical_count} taux identiques ignorés.",
        level='info',
        source_obj=source,
        zone_obj=source.zone
    )
    return f"Traitement terminé. {injected_count} taux injectés/mis à jour. {skipped_identical_count} taux identiques ignorés."