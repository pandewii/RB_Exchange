import os
import json
import subprocess
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.permissions import IsAdminTechniqueOnly
from core.models import Source, ScrapedCurrencyRaw, ZoneMonetaire
from decimal import Decimal # Ajout de l'import pour Decimal
from datetime import datetime # Importation nécessaire pour datetime.strptime

class SourceTauxCreateView(APIView):
    permission_classes = [IsAdminTechniqueOnly]

    def post(self, request, *args, **kwargs):
        zone_id = request.data.get('zone_id')
        nom_source = request.data.get('nom_source')
        url_source = request.data.get('url_source')
        scraper_filename = request.data.get('scraper_filename')

        if not all([zone_id, nom_source, url_source, scraper_filename]):
            return Response(
                {"error": "Tous les champs (zone_id, nom_source, url_source, scraper_filename) sont requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            zone = ZoneMonetaire.objects.get(pk=zone_id)
        except ZoneMonetaire.DoesNotExist:
            return Response({"error": "La zone spécifiée n'existe pas."}, status=status.HTTP_404_NOT_FOUND)

        if Source.objects.filter(zone=zone).exists():
            return Response({"error": "Une source est déjà configurée pour cette zone."}, status=status.HTTP_409_CONFLICT)

        source = Source.objects.create(
            zone=zone,
            nom=nom_source,
            url_source=url_source,
            scraper_filename=scraper_filename
        )

        script_path = os.path.join(settings.BASE_DIR, 'scrapers', 'scrapers', scraper_filename)
        if not os.path.exists(script_path):
            source.delete() # Supprimer la source si le script n'est pas trouvé
            return Response(
                {"error": f"Le script du scraper '{scraper_filename}' est introuvable."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = subprocess.run(
                ['python', script_path], capture_output=True, text=True, check=True, timeout=60
            )
            scraped_data = json.loads(result.stdout)
            
            raw_entries = []
            for item in scraped_data:
                date_pub = item.get('date_publication')
                if date_pub:
                    try:
                        date_pub = datetime.strptime(date_pub, "%Y-%m-%d").date() # Assurez-vous que le scraper renvoie ce format
                    except ValueError: # Spécifier ValueError pour le parsing de date
                        date_pub = None # Si la date est mal formatée, on la met à None

                valeur_brute_decimal = Decimal('0.0')
                try:
                    if 'valeur' in item and item['valeur'] is not None:
                        # Capture ValueError pour la conversion Decimal, TypeError si item['valeur'] est None inattendument
                        valeur_brute_decimal = Decimal(str(item['valeur']).replace(',', '.'))
                except (ValueError, TypeError): # Spécifier ValueError et TypeError
                    pass # La valeur restera 0.0 si la conversion échoue


                raw_entries.append(ScrapedCurrencyRaw(
                    source=source,
                    date_publication_brut=date_pub, # Utilisation de la date potentiellement traitée
                    nom_devise_brut=item.get('nom_brut', ''),
                    code_iso_brut=item.get('code_iso', ''), # Assurez-vous que le scraper renvoie 'code_iso'
                    valeur_brute=valeur_brute_decimal, # Correction ici
                    multiplicateur_brut=int(item.get('unite', 1))
                ))
            
            ScrapedCurrencyRaw.objects.bulk_create(raw_entries)
            
            message = f"Source créée et {len(raw_entries)} devises récupérées avec succès."

        # Exceptions plus spécifiques pour l'exécution du scraper et le traitement des données
        except subprocess.TimeoutExpired as e:
            source.delete() # Supprimer la source si le scraper échoue au timeout
            message = f"Erreur: L'exécution du scraper a dépassé le temps imparti : {e}"
            return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except subprocess.CalledProcessError as e:
            source.delete() # Supprimer la source si le scraper échoue
            message = f"Erreur d'exécution du scraper (code {e.returncode}): {e.stderr}"
            return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except json.JSONDecodeError as e:
            source.delete() # Supprimer la source si le JSON est invalide
            message = f"Erreur: Le scraper n'a pas renvoyé de JSON valide : {e}"
            return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e: # Garder une capture générale pour les erreurs inattendues
            source.delete() # Supprimer la source pour toute erreur inattendue lors du scraping initial
            message = f"Source créée avec succès, mais l'exécution initiale du scraper a échoué : {e}"
            return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": message,
            "source": {
                "id": source.id,
                "nom": source.nom,
                "url": source.url_source,
                "scraper": source.scraper_filename
            }
        }, status=status.HTTP_201_CREATED)
