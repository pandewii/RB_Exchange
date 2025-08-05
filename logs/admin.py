from django.contrib import admin
from .models import LogEntry # UINotification is no longer imported

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'actor_display', 'impersonator_display', 'target_user_display', 'zone', 'source', 'level') 
    list_filter = ('action', 'level', 'zone', 'source', 'timestamp', 'actor__role', 'impersonator__role', 'target_user__role') 
    search_fields = ('action', 'details', 'actor__email', 'impersonator__email', 'target_user__email', 'zone__nom', 'source__nom') 
    readonly_fields = ('actor', 'impersonator', 'target_user', 'action', 'details', 'timestamp', 'level', 'zone', 'source') 
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def actor_display(self, obj):
        return obj.actor.email if obj.actor else "Système" 
    actor_display.short_description = "Acteur"

    def impersonator_display(self, obj):
        return obj.impersonator.email if obj.impersonator else "-" 
    impersonator_display.short_description = "Agissait comme"
    
    def target_user_display(self, obj):
        return obj.target_user.email if obj.target_user else "-" 
    target_user_display.short_description = "Cible"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# UINotificationAdmin registration is completely removed from this file.