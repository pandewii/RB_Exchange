from django import template

# On crée une instance de la bibliothèque de templates de Django
register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permet de récupérer une valeur d'un dictionnaire en utilisant une clé
    directement dans un template Django.
    Exemple d'utilisation : {{ mon_dictionnaire|get_item:ma_cle }}
    """
    return dictionary.get(key)