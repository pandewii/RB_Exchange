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

    # L'action qui a été réalisée.
    action = models.CharField(max_length=100)

    # Une description textuelle de l'action pour une lecture facile.
    details = models.TextField()

    # La date et l'heure de l'action.
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        actor_email = self.actor.email if self.actor else "un utilisateur système"
        if self.impersonator:
            impersonator_email = self.impersonator.email if self.impersonator else "un utilisateur supprimé"
            return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {actor_email} (agissant comme {impersonator_email}) - {self.action}"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {actor_email} - {self.action}"