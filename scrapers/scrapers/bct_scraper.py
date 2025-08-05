#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import sys
import re
from datetime import datetime # Importation nécessaire

URL = "https://www.bct.gov.tn/bct/siteprod/cours.jsp"

def scraper_bct_exchange_rates():
    try:
        # Correction: Supprimez 'verify=False' et les avertissements si utilisés ici
        response = requests.get(URL, timeout=60)
        response.raise_for_status() # Lève une exception pour les codes d'erreur 4xx/5xx
    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion : {e}", file=sys.stderr)
        sys.exit(1)

    soup = BeautifulSoup(response.content, 'html.parser')

    # Récupération et normalisation de la date de publication au format YYYY-MM-DD
    date_publication_iso = None
    date_tag = soup.find(lambda tag: tag.name in ['h3', 'p', 'span', 'div'] and 'Journée du' in tag.get_text())
    if date_tag:
        match = re.search(r'\d{2}/\d{2}/\d{4}', date_tag.get_text())
        if match:
            try:
                # Convertir la date du format DD/MM/YYYY au format YYYY-MM-DD
                date_publication_iso = datetime.strptime(match.group(0), "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                # Gérer les erreurs de parsing de date si nécessaire, mais on passera None
                pass

    table = soup.find('table')
    if not table:
        print("Erreur : Aucune table n'a été trouvée sur la page.", file=sys.stderr)
        sys.exit(1)

    exchange_rates_list = []
    rows = table.find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        # S'assurer qu'il y a suffisamment de cellules pour éviter IndexError
        if len(cells) >= 4:
            try:
                # Convertir valeur en float et assurer un nom brut si manquant
                nom_brut = cells[0].get_text(strip=True)
                code_iso = cells[1].get_text(strip=True)
                unite = int(cells[2].get_text(strip=True))
                valeur = float(cells[3].get_text(strip=True).replace(',', '.'))

                rate_data = {
                    "date_publication": date_publication_iso, # Utilisation de la date normalisée
                    "nom_brut": nom_brut if nom_brut else code_iso, # Assurer un nom brut si possible, sinon utiliser code_iso
                    "code_iso": code_iso,
                    "unite": unite,
                    "valeur": valeur
                }
                exchange_rates_list.append(rate_data)
            except (ValueError, IndexError):
                pass # Ignore les lignes mal formatées (comme l'en-tête)

    print(json.dumps(exchange_rates_list, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    scraper_bct_exchange_rates()
