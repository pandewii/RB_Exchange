from django.contrib import admin
from .models import LogEntry

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste des logs
    list_display = ('timestamp', 'actor_display', 'impersonator_display', 'action')
    
    # Filtres
    list_filter = ('action', 'timestamp')
    
    # Champs de recherche
    search_fields = ('actor__email', 'impersonator__email', 'action', 'details')
    
    # Champs en lecture seule pour éviter les modifications manuelles des logs
    readonly_fields = ('actor', 'impersonator', 'action', 'details', 'timestamp')
    
    # Permet de naviguer par date
    date_hierarchy = 'timestamp'
    
    # Ordonnancement par défaut (le plus récent en premier)
    ordering = ('-timestamp',)

    # Méthode personnalisée pour afficher l'email de l'acteur
    def actor_display(self, obj):
        return obj.actor.email if obj.actor else "N/A"
    actor_display.short_description = "Acteur"

    # Méthode personnalisée pour afficher l'email de l'impersonator
    def impersonator_display(self, obj):
        return obj.impersonator.email if obj.impersonator else "N/A"
    impersonator_display.short_description = "Agissait comme"

    # Désactiver les boutons d'ajout et de suppression pour les LogEntry
    # Les logs doivent être créés par le système, non manuellement.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
