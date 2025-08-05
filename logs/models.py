# logs/models.py
from django.db import models
from django.conf import settings
from core.models import ZoneMonetaire, Source

class LogEntry(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='action_logs')
    impersonator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='impersonated_action_logs')
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_action_logs')

    zone = models.ForeignKey(
        ZoneMonetaire,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='zone_related_logs'
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='source_related_logs'
    )

    action = models.CharField(max_length=100)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=20, default='info')
    currency_code = models.CharField(max_length=10, null=True, blank=True) # <-- ADD THIS LINE

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        actor_email = self.actor.email if self.actor else "Système"
        impersonator_info = f" (agissant comme {self.impersonator.email})" if self.impersonator else ""
        zone_info = f" [Zone: {self.zone.nom}]" if self.zone else ""
        source_info = f" [Source: {self.source.nom}]" if self.source else ""
        currency_info = f" [Currency: {self.currency_code}]" if self.currency_code else "" # Add to str
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {actor_email}{impersonator_info} - {self.action}{zone_info}{source_info}{currency_info}"