from logs.models import LogEntry
from users.models import CustomUser
from core.models import ZoneMonetaire, Source
import sys

def log_action(actor_id=None, action=None, details=None, level='info',
               zone_id=None, source_id=None, target_user_id=None, impersonator_id=None,
               currency_code=None, zone_obj=None, source_obj=None):
    """
    Enregistre une action dans le système de logs. Ignore certains logs "bruit" (non utiles).
    """

    # 🚫 Filtrage des logs bruit de niveau info
    noisy_ignored = ['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY']
    if action in noisy_ignored and level.lower() == 'info':
        return

    # Chargement des objets (users)
    actor = None
    if actor_id:
        try:
            actor = CustomUser.objects.get(pk=actor_id)
        except CustomUser.DoesNotExist:
            print(f"[log_action]  Actor ID {actor_id} not found", file=sys.stderr)

    impersonator = None
    if impersonator_id:
        try:
            impersonator = CustomUser.objects.get(pk=impersonator_id)
        except CustomUser.DoesNotExist:
            print(f"[log_action]  Impersonator ID {impersonator_id} not found", file=sys.stderr)

    target_user = None
    if target_user_id:
        try:
            target_user = CustomUser.objects.get(pk=target_user_id)
        except CustomUser.DoesNotExist:
            print(f"[log_action]  Target User ID {target_user_id} not found", file=sys.stderr)

    # Chargement zone/source
    if zone_obj is None and zone_id:
        try:
            zone_obj = ZoneMonetaire.objects.get(pk=zone_id)
        except ZoneMonetaire.DoesNotExist:
            print(f"[log_action]  Zone ID {zone_id} not found", file=sys.stderr)

    if source_obj is None and source_id:
        try:
            source_obj = Source.objects.get(pk=source_id)
        except Source.DoesNotExist:
            print(f"[log_action]  Source ID {source_id} not found", file=sys.stderr)

    # Enregistrement en base
    try:
        LogEntry.objects.create(
            actor=actor,
            impersonator=impersonator,
            target_user=target_user,
            zone=zone_obj,
            source=source_obj,
            action=action,
            details=details,
            level=level,
            currency_code=currency_code
        )
    except Exception as e:
        print(f"[log_action]  Erreur BD : {e} – Action={action}", file=sys.stderr)
