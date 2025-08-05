from .models import Source, DeviseAlias, ActivatedCurrency, ExchangeRate, Devise
from datetime import datetime
from decimal import Decimal
import sys
from logs.utils import log_action
from django.db import transaction
from django.db.models import Q

@transaction.atomic
def process_and_inject_rates(source_id: int):
    try:
        source = Source.objects.select_related('zone').get(pk=source_id)
    except Source.DoesNotExist:
        log_action(actor_id=None, action='PIPELINE_ERROR',
                   details=f"Source ID {source_id} introuvable", level='critical')
        return "Erreur : Source non trouvée."

    latest_raw = source.raw_data.filter(date_publication_brut__isnull=False) \
                                .order_by('-date_publication_brut', '-date_scraping').first()
    if not latest_raw:
        log_action(actor_id=None, action='PIPELINE_NO_RAW_DATA',
                   details=f"Aucune donnée brute pour la source {source.nom}", level='warning')
        return "Aucune donnée brute récente à traiter."

    latest_date = latest_raw.date_publication_brut
    raw_today = source.raw_data.filter(date_publication_brut=latest_date)

    aliases = {
        alias.alias: alias.devise_officielle
        for alias in DeviseAlias.objects.select_related('devise_officielle').all()
    }

    active_codes = {
        ac.devise.code for ac in ActivatedCurrency.objects.filter(zone=source.zone, is_active=True)
    }

    injected_count = 0
    skipped_identical_count = 0

    for raw in raw_today:
        official_devise = aliases.get(raw.nom_devise_brut) or aliases.get(raw.code_iso_brut)
        if not official_devise or official_devise.code not in active_codes:
            continue

        try:
            valeur = raw.valeur_brute
            multiplicateur = Decimal(raw.multiplicateur_brut) if raw.multiplicateur_brut > 0 else Decimal('1')
            taux_normalise = (valeur / multiplicateur).quantize(Decimal('0.000000001'))
        except Exception as e:
            log_action(actor_id=None, action='PIPELINE_CALCULATION_ERROR',
                       details=f"Erreur de calcul pour {raw.code_iso_brut}: {e}", level='error')
            continue

        # Recherche s’il existe déjà un taux pour la même devise/date/zone
        existing = ExchangeRate.objects.filter(
            devise=official_devise,
            zone=source.zone,
            date_publication=latest_date
        ).first()

        if existing:
            if (
                existing.taux_source == valeur and
                existing.multiplicateur_source == raw.multiplicateur_brut and
                existing.taux_normalise == taux_normalise
            ):
                # Identique : juste maj is_latest
                if not existing.is_latest:
                    existing.is_latest = True
                    existing.save(update_fields=['is_latest'])
                skipped_identical_count += 1
            else:
                # Valeurs changées : maj
                existing.taux_source = valeur
                existing.multiplicateur_source = raw.multiplicateur_brut
                existing.taux_normalise = taux_normalise
                existing.is_latest = True
                existing.save()
                injected_count += 1
        else:
            # Nouveau taux : création
            ExchangeRate.objects.create(
                devise=official_devise,
                zone=source.zone,
                date_publication=latest_date,
                taux_source=valeur,
                multiplicateur_source=raw.multiplicateur_brut,
                taux_normalise=taux_normalise,
                is_latest=True
            )
            injected_count += 1

        # On met tous les autres `is_latest=True` pour cette devise/zone à False
        ExchangeRate.objects.filter(
            devise=official_devise,
            zone=source.zone,
            is_latest=True
        ).exclude(date_publication=latest_date).update(is_latest=False)

    log_action(
        actor_id=None,
        action='PIPELINE_EXECUTION_COMPLETED',
        details=f"{source.nom} ({source.zone.nom}) → {injected_count} taux injectés, {skipped_identical_count} identiques ignorés.",
        level='info'
    )
    return f"Traitement terminé. {injected_count} taux injectés/mis à jour. {skipped_identical_count} taux identiques ignorés."
