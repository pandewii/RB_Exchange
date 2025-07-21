#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from dotenv import load_dotenv


# 🔐 Clé API ScraperAPI
load_dotenv()
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")
TARGET_URL = "https://www.bank-of-algeria.dz/taux-de-change-journalier/"

def fetch_page_content():
    try:
        response = httpx.get(
            "https://api.scraperapi.com",
            params={
                "api_key": SCRAPER_API_KEY,
                "url": TARGET_URL,
                "render": "true",
                "wait_for_selector": "table"
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        raise Exception(f"[ScraperAPI] Échec de la requête : {e}")
    except httpx.HTTPStatusError as e:
        raise Exception(f"[ScraperAPI] Erreur HTTP : {e.response.status_code} {e.response.reason_phrase}")

def parse_exchange_rates(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one("table")

    if not table:
        raise Exception("❌ Aucune table trouvée sur la page.")

    headers = table.select("th")
    latest_col_index = None
    date_raw = None

    for idx, th in enumerate(headers):
        txt = th.get_text(strip=True)
        if re.match(r"\d{2}-\d{2}-\d{4}", txt):
            date_raw = txt
            latest_col_index = idx
            break

    if latest_col_index is None:
        raise Exception("❌ Colonne de date non trouvée.")

    try:
        date_iso = datetime.strptime(date_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        raise Exception(f"❌ Erreur parsing date : {date_raw}")

    data = []
    for row in table.select("tr")[1:]:
        cols = row.select("td")
        if len(cols) > latest_col_index and cols[0].text.strip():
            try:
                code = cols[0].text.strip().upper()
                valeur_str = cols[latest_col_index].text.strip().replace(",", ".")
                valeur = float(valeur_str)
                data.append({
                    "date_publication": date_iso,
                    "nom_brut": code,
                    "code_iso": code,
                    "unite": 1,
                    "valeur": valeur
                })
            except Exception:
                continue

    return data

def run():
    try:
        html = fetch_page_content()
        rates = parse_exchange_rates(html)
        print(json.dumps(rates, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    run()
