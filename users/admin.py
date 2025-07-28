from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Champs affichés dans la liste des utilisateurs
    list_display = ('email', 'username', 'role', 'is_active', 'is_staff', 'zone_display')
    
    # Filtres pour la liste des utilisateurs
    list_filter = ('is_active', 'is_staff', 'role', 'zone')
    
    # Champs de recherche
    search_fields = ('email', 'username')
    
    # Ordonnancement par défaut
    ordering = ('email',)

    # Configuration des formulaires d'édition (fieldsets pour la page d'édition)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': ('username', 'role', 'zone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )

    # Configuration des formulaires de création (add_fieldsets pour la page de création)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'password2')}
        ),
        ('Informations personnelles', {'fields': ('username', 'role', 'zone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    
    # 'raw_id_fields' est utile pour les ForeignKey avec un grand nombre d'objets,
    # cela transforme le select en champ de texte avec une loupe de recherche.
    # Utile pour 'zone' si beaucoup de zones.
    raw_id_fields = ('zone',)

    # Méthode pour afficher le nom de la zone
    def zone_display(self, obj):
        return obj.zone.nom if obj.zone else "-"
    zone_display.short_description = "Zone Assignée"
