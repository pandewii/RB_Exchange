# scrapers/tasks.py

import os
import json
import subprocess
from django.conf import settings
from celery import shared_task
from core.models import Source, ScrapedCurrencyRaw, ZoneMonetaire
from core.pipeline import process_and_inject_rates
from datetime import datetime
from decimal import Decimal
import sys
from logs.utils import log_action

@shared_task(name="scrapers.tasks.run_scraper_for_source")
def run_scraper_for_source(source_id):
    """
    Tâche Celery générique pour exécuter le scraper associé à une Source,
    insérer les données brutes et déclencher le pipeline.
    Maintenant, inclut une vérification pour s'assurer que la zone associée est active.
    """
    source = None
    zone = None
    try:
        source = Source.objects.get(pk=source_id)
        zone = source.zone

        # NEW CHECK: Prevent pipeline execution if the zone is inactive
        if not zone or not zone.is_active:
            log_action(
                actor_id=None, # System action
                action='PIPELINE_BLOCKED_ZONE_INACTIVE',
                details=f"Pipeline bloqué pour la source '{source.nom}' (ID: {source.pk}) car la zone '{zone.nom if zone else 'N/A'}' (ID: {zone.pk if zone else 'N/A'}) est inactive ou non assignée.",
                level='warning', # Level is warning as it's a block, not just info
                zone_obj=zone,
                source_obj=source
            )
            return f"Pipeline skipped for source {source_id}: Zone is inactive or not assigned."

        script_path = os.path.join(settings.SCRAPERS_DIR, source.scraper_filename)
        if not os.path.exists(script_path):
            log_action(
                actor_id=None,
                action='SCRAPER_SCRIPT_NOT_FOUND',
                details=f"Erreur: Le script du scraper '{source.scraper_filename}' pour la source '{source.nom}' (ID: {source.pk}) est introuvable.",
                level='error',
                zone_obj=zone,
                source_obj=source
            )
            return f"Erreur : Le script du scraper {source.scraper_filename} est introuvable."

        result = subprocess.run(
            ['python', script_path], capture_output=True, text=True, check=False, timeout=120 # Changed check=True to check=False to capture stderr and handle it
        )

        if result.returncode != 0: # Scraper script returned an error
            log_action(
                actor_id=None,
                action='SCRAPER_EXECUTION_ERROR',
                details=f"Le script du scraper '{source.scraper_filename}' pour la source '{source.nom}' (ID: {source.pk}) a échoué. Code de sortie: {result.returncode}. Erreur (stderr): {result.stderr}",
                level='error',
                zone_obj=zone,
                source_obj=source
            )
            return f"Erreur d'exécution du scraper pour la source {source.nom}."


        try:
            scraped_data = json.loads(result.stdout)
            if not scraped_data: # Handle empty JSON array or object
                raise json.JSONDecodeError("Scraper returned empty data.", result.stdout, 0)

        except json.JSONDecodeError as e:
            log_action(
                actor_id=None,
                action='SCRAPER_INVALID_JSON',
                details=f"Erreur: Le scraper pour la source '{source.nom}' (ID: {source.pk}) n'a pas renvoyé de JSON valide. Output: '{result.stdout[:500]}' Détails: {e}",
                level='error',
                zone_obj=zone,
                source_obj=source
            )
            return f"Erreur: Le scraper pour la source {source.nom} n'a pas renvoyé de JSON valide."


        # Logique de suppression des données brutes pour la date cible
        target_date = None
        if scraped_data and scraped_data[0].get('date_publication'):
            try:
                target_date = datetime.strptime(scraped_data[0]['date_publication'], "%Y-%m-%d").date()
                # Only delete if target_date is successfully parsed
                ScrapedCurrencyRaw.objects.filter(source=source, date_publication_brut=target_date).delete()
            except ValueError:
                log_action(
                    actor_id=None,
                    action='RAW_DATA_DATE_PARSE_ERROR',
                    details=f"Warning: Mauvais format de date dans le JSON du scraper pour la source '{source.nom}'. Date: {scraped_data[0].get('date_publication')}",
                    level='warning',
                    zone_obj=zone,
                    source_obj=source
                )
        
        raw_entries = []
        for item in scraped_data:
            date_pub = None
            if item.get('date_publication'):
                try:
                    date_pub = datetime.strptime(item['date_publication'], "%Y-%m-%d").date()
                except ValueError:
                    log_action(
                        actor_id=None,
                        action='RAW_DATA_DATE_PARSE_ERROR',
                        details=f"Warning: Impossible de parser la date '{item['date_publication']}' pour la source '{source.nom}'.",
                        level='warning',
                        zone_obj=zone,
                        source_obj=source
                    )

            valeur = Decimal('0.0')
            try:
                if item.get('valeur') is not None:
                    valeur = Decimal(str(item['valeur']).replace(',', '.'))
            except (ValueError, TypeError):
                log_action(
                    actor_id=None,
                    action='RAW_DATA_VALUE_PARSE_ERROR',
                    details=f"Warning: Valeur incorrecte pour '{item.get('code_iso', 'N/A')}' pour la source '{source.nom}'. Valeur: '{item.get('valeur', 'N/A')}'",
                    level='warning',
                    zone_obj=zone,
                    source_obj=source
                )

            raw_entries.append(ScrapedCurrencyRaw(
                source=source,
                date_publication_brut=date_pub,
                nom_devise_brut=item.get('nom_brut', ''),
                code_iso_brut=item.get('code_iso', ''),
                valeur_brute=valeur,
                multiplicateur_brut=int(item.get('unite', 1))
            ))
        
        if raw_entries:
            ScrapedCurrencyRaw.objects.bulk_create(raw_entries)
        
        # Trigger pipeline processing
        processing_result = process_and_inject_rates(source.pk) # Assuming process_and_inject_rates also handles logging
        
        log_action(
            actor_id=None,
            action='PIPELINE_EXECUTION_SUCCESS',
            details=f"Pipeline exécuté avec succès pour la source '{source.nom}' (ID: {source.pk}) de la zone '{zone.nom}'. {len(raw_entries)} devises brutes traitées. Résultat pipeline: {processing_result}",
            level='info',
            zone_obj=zone,
            source_obj=source
        )
        return f"Succès : {len(raw_entries)} devises brutes récupérées pour la source {source.nom}. Pipeline: {processing_result}"

    # General exception handling for any unhandled errors in the task
    except Source.DoesNotExist:
        log_action(
            actor_id=None,
            action='SCRAPER_EXECUTION_FAILED',
            details=f"Erreur critique: Source avec l'ID {source_id} non trouvée lors de l'exécution du scraper Celery.",
            level='critical'
        )
        return f"Erreur critique : Source avec l'ID {source_id} non trouvée."
    except Exception as e:
        # Catch-all for any other unexpected errors during the task
        log_action(
            actor_id=None,
            action='PIPELINE_UNEXPECTED_ERROR',
            details=f"Erreur inattendue lors de l'exécution du scraper/pipeline pour la source '{source.nom if source else 'ID non spécifié'}' (ID: {source.pk if source else source_id}). Détails: {e}",
            level='critical',
            zone_obj=zone,
            source_obj=source
        )
        return f"Erreur interne lors du traitement de la source {source.nom if source else 'ID non spécifié'} (ID: {source.pk if source else source_id}) : {e}"