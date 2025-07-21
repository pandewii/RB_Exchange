# scrapers/tasks.py

import os
import json
import subprocess
from django.conf import settings
from celery import shared_task
from core.models import Source, ScrapedCurrencyRaw
from core.pipeline import process_and_inject_rates
from datetime import datetime
from decimal import Decimal
import sys # Importation du module sys

@shared_task(name="scrapers.tasks.run_scraper_for_source")
def run_scraper_for_source(source_id):
    """
    Tâche Celery générique pour exécuter le scraper associé à une Source,
    insérer les données brutes et déclencher le pipeline.
    """
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        return f"Erreur : Source avec l'ID {source_id} non trouvée."

    script_path = os.path.join(settings.SCRAPERS_DIR, source.scraper_filename)
    if not os.path.exists(script_path):
        return f"Erreur : Le script du scraper {source.scraper_filename} est introuvable."

    try:
        result = subprocess.run(
            ['python', script_path], capture_output=True, text=True, check=True, timeout=120
        )
        scraped_data = json.loads(result.stdout)

        # La logique de suppression doit d'abord déterminer la date cible de manière fiable
        target_date = None
        if scraped_data and scraped_data[0].get('date_publication'):
            try:
                target_date = datetime.strptime(scraped_data[0]['date_publication'], "%Y-%m-%d").date()
                ScrapedCurrencyRaw.objects.filter(source=source, date_publication_brut=target_date).delete()
            except ValueError: # Spécifier ValueError pour le parsing de date
                print(f"Warning: Mauvais format de date dans le JSON du scraper.", file=sys.stderr)
        
        raw_entries = []
        for item in scraped_data:
            date_pub = None
            if item.get('date_publication'):
                try:
                    date_pub = datetime.strptime(item['date_publication'], "%Y-%m-%d").date()
                except ValueError:
                    print(f"Warning: Impossible de parser la date {item['date_publication']}", file=sys.stderr)

            valeur = Decimal('0.0')
            try:
                if item.get('valeur') is not None:
                    valeur = Decimal(str(item['valeur']).replace(',', '.'))
            except (ValueError, TypeError):
                print(f"Warning: Valeur incorrecte pour {item.get('code_iso')}.", file=sys.stderr)

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
        
        processing_result = process_and_inject_rates(source.pk)
        
        return f"Succès : {len(raw_entries)} devises récupérées pour la source {source.nom}. Pipeline: {processing_result}"

    # Exceptions plus spécifiques d'abord
    except subprocess.TimeoutExpired as e:
        print(f"Erreur: Le scraper pour la source {source.nom} a dépassé le temps imparti (timeout={e.timeout}s).", file=sys.stderr)
        return f"Erreur: Scraper pour {source.nom} a dépassé le temps imparti."
    except subprocess.CalledProcessError as e:
        print(f"Erreur d'exécution du scraper pour la source {source.nom} (code {e.returncode}): {e.stderr}", file=sys.stderr)
        return f"Erreur d'exécution du scraper pour la source {source.nom} : {e.stderr}"
    except json.JSONDecodeError as e:
        print(f"Erreur: Le scraper pour la source {source.nom} n'a pas renvoyé de JSON valide. Détails: {e}", file=sys.stderr)
        return f"Erreur: Le scraper pour la source {source.nom} n'a pas renvoyé de JSON valide."
    except Exception as e: # Capture toutes les autres exceptions inattendues
        print(f"Erreur inattendue lors de l'exécution du scraper pour la source {source.nom} : {e}", file=sys.stderr)
        return f"Erreur interne lors du traitement de la source {source.nom} : {e}"
