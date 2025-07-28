# logs/models.py

from django.db import models
from django.conf import settings

class LogEntry(models.Model):
    # L'utilisateur qui a réellement cliqué sur le bouton.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='action_logs'
    )

    # NOUVEAU CHAMP : Si l'acteur agissait en tant que quelqu'un d'autre.
    # Ce champ sera rempli uniquement lors d'un "switch".
    impersonator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, # Ce champ est optionnel
        related_name='impersonated_action_logs'
    )
    
    # AJOUT : L'utilisateur cible de l'action, si applicable.
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, # Ce champ est optionnel
        related_name='targeted_action_logs' # Nom distinct pour related_name
    )

    # L'action qui a été réalisée.
    action = models.CharField(max_length=100)

    # Une description textuelle de l'action pour une lecture facile.
    details = models.TextField()

    # La date et l'heure de l'action.
    timestamp = models.DateTimeField(auto_now_add=True)

    # AJOUT : Niveau de log (info, warning, error, critical)
    level = models.CharField(max_length=20, default='info')

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        actor_email = self.actor.email if self.actor else "un utilisateur système"
        if self.impersonator:
            impersonator_email = self.impersonator.email if self.impersonator else "un utilisateur supprimé"
            return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {actor_email} (agissant comme {impersonator_email}) - {self.action}"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {actor_email} - {self.action}"


# AJOUT : Nouveau modèle UINotification
class UINotification(models.Model):
    """
    Modèle pour les notifications affichées dans l'interface utilisateur.
    Chaque notification est liée à un LogEntry.
    """
    # Message à afficher à l'utilisateur
    message = models.TextField()
    
    # Niveau de la notification ('info', 'warning', 'error', 'critical')
    level = models.CharField(max_length=20, default='info')
    
    # Indique si la notification a été lue par l'utilisateur
    is_read = models.BooleanField(default=False)
    
    # Date et heure de création de la notification
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Lien vers le LogEntry qui a déclenché cette notification (peut être null si la notif n'a pas de log direct)
    related_log_entry = models.ForeignKey(
        LogEntry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ui_notifications'
    )
    
    # L'utilisateur spécifique à notifier (peut être null si notif générale pour un rôle)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, # Si l'utilisateur est supprimé, ses notifications le sont aussi
        null=True, blank=True,
        related_name='user_notifications'
    )

    class Meta:
        verbose_name = "Notification UI"
        verbose_name_plural = "Notifications UI"
        ordering = ('-timestamp',) # Les notifications les plus récentes en premier

    def __str__(self):
        return f"[{self.level.upper()}] {self.message[:50]}... ({'Lu' if self.is_read else 'Non lu'})"
