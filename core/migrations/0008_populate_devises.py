# Fichier : core/migrations/0008_populate_devises.py

from django.db import migrations

# Liste des devises officielles à insérer
OFFICIAL_CURRENCIES = [
    {"code": "AED", "nom": "Dirham des Émirats Arabes Unis"},
    {"code": "DZD", "nom": "Dinar Algérien"},
    {"code": "BHD", "nom": "Dinar de Bahreïn"},
    {"code": "CAD", "nom": "Dollar Canadien"},
    {"code": "USD", "nom": "Dollar des USA"},
    {"code": "EUR", "nom": "Euro"},
    {"code": "GBP", "nom": "Livre Sterling"},
    {"code": "JPY", "nom": "Yen Japonais"},
    {"code": "KWD", "nom": "Dinar Koweïtien"},
    {"code": "LYD", "nom": "Dinar Libyen"},
    {"code": "MAD", "nom": "Dirham Marocain"},
    {"code": "MRU", "nom": "Ouguiya Mauritanien"},
    {"code": "NOK", "nom": "Couronne Norvégienne"},
    {"code": "QAR", "nom": "Riyal Qatari"},
    {"code": "SAR", "nom": "Riyal Saoudien"},
    {"code": "SEK", "nom": "Couronne Suédoise"},
    {"code": "CHF", "nom": "Franc Suisse"},
    {"code": "TND", "nom": "Dinar Tunisien"},
    {"code": "CNY", "nom": "Yuan Chinois"},
    {"code": "DKK", "nom": "Couronne Danoise"},
]

def populate_devises(apps, schema_editor):
    """
    Cette fonction sera exécutée par la migration.
    Elle récupère le modèle Devise et y insère toutes les devises de notre liste.
    """
    Devise = apps.get_model('core', 'Devise')
    
    devises_to_create = []
    for currency_data in OFFICIAL_CURRENCIES:
        devises_to_create.append(
            Devise(code=currency_data["code"], nom=currency_data["nom"])
        )
    
    # Insère toutes les devises en une seule requête pour être efficace
    # ignore_conflicts=True évite une erreur si vous relancez la migration sur une base déjà peuplée.
    Devise.objects.bulk_create(devises_to_create, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        # Cette ligne doit pointer vers votre migration précédente.
        # Comme votre nouveau fichier est le 0008, la précédente est probablement la 0007.
        ('core', '0007_scrapedcurrencyraw_date_publication_brut'), # <-- VÉRIFIEZ CE NUMÉRO
    ]

    operations = [
        migrations.RunPython(populate_devises),
    ]