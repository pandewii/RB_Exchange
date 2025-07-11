import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys
import time
import tempfile

URL = "https://www.bank-of-algeria.dz/taux-de-change-journalier/"

def scraper_boa_exchange_rates():
    try:
        # Créer un profil Chrome temporaire pour éviter les erreurs de session/cookies
        chrome_profile_dir = tempfile.mkdtemp()

        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--user-data-dir={chrome_profile_dir}')

        print("Démarrage de Chrome avec profil isolé...")
        driver = uc.Chrome(options=options)

        try:
            print("Connexion à la Banque d'Algérie...")
            driver.get(URL)
        except Exception as e:
            print(f"❗ 1ère tentative échouée : {e}")
            print("Nouvelle tentative après 5 secondes...")
            time.sleep(5)
            driver.get(URL)  # Retry

        print("Page chargée. Extraction en cours...")
        time.sleep(5)  # Laisse le temps à la page de se stabiliser
        soup = BeautifulSoup(driver.page_source, 'html.parser')

    except Exception as e:
        print(f"Erreur Selenium : {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            driver.quit()
        except:
            pass

    # Analyse du tableau HTML
    table = soup.find('table')
    if not table:
        print("Erreur : Aucune table trouvée.", file=sys.stderr)
        sys.exit(1)

    headers = table.find_all('th')
    date_headers_raw = [th.get_text(strip=True) for th in headers if th.get_text(strip=True).count('-') == 2]

    if not date_headers_raw:
        print("Erreur : Dates non trouvées.", file=sys.stderr)
        sys.exit(1)

    latest_date_raw = date_headers_raw[0]
    try:
        latest_date_iso = datetime.strptime(latest_date_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        print(f"Erreur de format de date : {latest_date_raw}", file=sys.stderr)
        sys.exit(1)

    all_ths = table.find('tr').find_all('th')
    latest_col_index = None
    for idx, th in enumerate(all_ths):
        if th.get_text(strip=True) == latest_date_raw:
            latest_col_index = idx
            break

    if latest_col_index is None:
        print("Erreur : Colonne de la date la plus récente introuvable.", file=sys.stderr)
        sys.exit(1)

    exchange_rates = []
    rows = table.find_all('tr')[1:]

    for row in rows:
        cells = row.find_all('td')
        if len(cells) > latest_col_index:
            try:
                code_iso = cells[0].get_text(strip=True)
                valeur_str = cells[latest_col_index].get_text(strip=True).replace(',', '.')
                valeur = float(valeur_str)
                nom_brut = code_iso
                exchange_rates.append({
                    "date_publication": latest_date_iso,
                    "nom_brut": nom_brut,
                    "code_iso": code_iso,
                    "unite": 1,
                    "valeur": valeur
                })
            except Exception:
                continue

    print(json.dumps(exchange_rates, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    scraper_boa_exchange_rates()
