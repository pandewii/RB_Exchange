# logs/utils.py

from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.db.models import Q
import sys
from datetime import datetime

def log_action(actor_id, action, details, impersonator_id=None, target_user_id=None, level='info', zone_id=None, currency_code=None, source_id=None):
    """
    Enregistre une action dans le système de logs et génère des notifications UI ciblées.
    Les messages 'details' sont maintenant supposés être construits de manière sémantique
    au point d'appel dans les vues.
    AJOUT: zone_id, currency_code, source_id pour un ciblage plus précis des notifications.
    """
    actor = None
    if actor_id:
        try:
            actor = CustomUser.objects.get(pk=actor_id)
        except CustomUser.DoesNotExist:
            print(f"Warning: Actor with ID {actor_id} not found for log_action. Log will proceed without actor.", file=sys.stderr)
            pass # Continuer sans acteur si non trouvé

    impersonator = None
    if impersonator_id:
        try:
            impersonator = CustomUser.objects.get(pk=impersonator_id)
        except CustomUser.DoesNotExist:
            print(f"Warning: Impersonator with ID {impersonator_id} not found for log_action. Log will proceed without impersonator.", file=sys.stderr)
            pass # Continuer sans impersonateur si non trouvé

    target_user = None
    if target_user_id:
        try:
            target_user = CustomUser.objects.get(pk=target_user_id)
        except CustomUser.DoesNotExist:
            print(f"Warning: Target user with ID {target_user_id} not found for log_action. Log will proceed without target user.", file=sys.stderr)
            pass # Continuer sans utilisateur cible si non trouvé

    # Créer l'entrée de log principale (TOUJOURS créée)
    log_entry = LogEntry.objects.create(
        actor=actor,
        impersonator=impersonator,
        target_user=target_user,
        action=action,
        details=details, # Utilise le message 'details' déjà enrichi
        level=level,
        # IMPORTANT: Si vous avez ajouté zone_id, currency_code, source_id
        # comme champs directs dans le modèle LogEntry, ils devraient être passés ici.
        # Pour l'instant, ils sont utilisés pour le ciblage des notifications.
    )

    # --- LOGIQUE DE NOTIFICATION UI AFFINÉE ---
    # Déterminer si une notification UI doit être générée et pour qui.
    dest_user_ids = set() # Utiliser un set pour éviter les doublons (ID utilisateur)

    # Pré-charger les PKs des SuperAdmins et Admin Techs actifs pour des recherches rapides
    superadmins_active_pks = set(CustomUser.objects.filter(role='SUPERADMIN', is_active=True).values_list('pk', flat=True))
    admin_techs_active_pks = set(CustomUser.objects.filter(role='ADMIN_TECH', is_active=True).values_list('pk', flat=True))
    
    # --- Règles de génération des notifications ---

    # Règle 1: Les logs de niveau 'warning', 'error', 'critical' génèrent TOUJOURS une notification UI
    if level in ['warning', 'error', 'critical']:
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks) 
        
        # Si l'erreur/warning est liée à une zone, notifier les AdminZones concernés
        if zone_id:
            dest_user_ids.update(CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))
        
        # Notifier l'acteur, l'impersonateur, ou la cible si c'est un ADMIN_ZONE ou WS_USER et qu'ils ne sont pas déjà inclus
        if actor and actor.is_active and actor.pk not in dest_user_ids and actor.role in ['ADMIN_ZONE', 'WS_USER']:
            dest_user_ids.add(actor.pk)
        if impersonator and impersonator.is_active and impersonator.pk not in dest_user_ids and impersonator.role in ['ADMIN_ZONE', 'WS_USER']:
            dest_user_ids.add(impersonator.pk)
        if target_user and target_user.is_active and target_user.pk not in dest_user_ids and target_user.role in ['ADMIN_ZONE', 'WS_USER']:
            dest_user_ids.add(target_user.pk)

    # Règle 2: Les logs de niveau 'info' génèrent des notifications UI UNIQUEMENT pour des actions spécifiques.
    # Ces actions sont celles qui représentent un changement important d'état pour les admins.
    # Les logs de type "FAILED" (qui affichent déjà des erreurs UI) sont exclus pour éviter la redondance.
    elif action in [
        "ADMIN_CREATED", "CONSUMER_CREATED", "USER_MODIFIED", "USER_DELETED", "USER_STATUS_TOGGLED",
        "USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION", "ZONE_CREATED", "ZONE_DELETED",
        "ZONE_STATUS_TOGGLED", "ZONE_PROPERTIES_UPDATED", "SOURCE_CONFIGURED", "SOURCE_MODIFIED",
        "SOURCE_DELETED", "SCHEDULE_CREATED", "SCHEDULE_MODIFIED", "SCHEDULE_DELETED",
        "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED", "CURRENCY_ACTIVATION_TOGGLED",
        # Actions système importantes qui ne sont pas des erreurs mais des infos critiques (si pertinent)
        "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR", "SCRAPER_INVALID_JSON", "SCRAPER_UNEXPECTED_ERROR", # Ces-ci sont des erreurs, mais étaient niveau info dans l'ancienne logique
        "RAW_DATA_DATE_PARSE_ERROR", "RAW_DATA_VALUE_PARSE_ERROR", "PIPELINE_CALCULATION_ERROR",
        "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START",
    ]:
        # Par défaut, les SuperAdmins et Admin Techs sont informés de ces actions
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)

        # Ciblage plus précis pour les actions spécifiques:
        # Actions concernant les Zones, Sources, Schedules, Alias (affectant infrastructure ou zone spécifique)
        if action in [
            "ZONE_CREATED", "ZONE_DELETED", "ZONE_STATUS_TOGGLED", "ZONE_PROPERTIES_UPDATED", 
            "SOURCE_CONFIGURED", "SOURCE_MODIFIED", "SOURCE_DELETED", 
            "SCHEDULE_CREATED", "SCHEDULE_MODIFIED", "SCHEDULE_DELETED",
            "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED"
        ]:
            if zone_id:
                # Notifier les Admin Zones de cette zone
                dest_user_ids.update(CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))
                # Notifier les WS_USER de cette zone (si pertinent, ex: alias impacte leur accès)
                # Décision: Pour l'instant, les WS_USER ne reçoivent pas de notifications UI automatiques pour ces actions.
                # dest_user_ids.update(CustomUser.objects.filter(role='WS_USER', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))
        
        # Actions liées au scraping et pipeline (erreurs système, généralement pour Admin Tech / SuperAdmin)
        elif action in [
            "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR", "SCRAPER_INVALID_JSON", "SCRAPER_UNEXPECTED_ERROR",
            "RAW_DATA_DATE_PARSE_ERROR", "RAW_DATA_VALUE_PARSE_ERROR", "PIPELINE_CALCULATION_ERROR",
            "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START"
        ]:
            if zone_id: # Si l'erreur pipeline est liée à une zone spécifique
                dest_user_ids.update(CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))

        # Actions de gestion de devises activées (Admin Zone)
        elif action == "CURRENCY_ACTIVATION_TOGGLED":
            if zone_id:
                # Notifier les Admin Zones de cette zone
                dest_user_ids.update(CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))
                # Notifier les WS_USER de cette zone (si pertinent pour leur accès aux taux)
                dest_user_ids.update(CustomUser.objects.filter(role='WS_USER', zone__pk=zone_id, is_active=True).values_list('pk', flat=True))
        
        # Actions utilisateur (création/modification/suppression/statut/impersonation)
        elif action in [
            "ADMIN_CREATED", "CONSUMER_CREATED", "USER_MODIFIED", "USER_DELETED", "USER_STATUS_TOGGLED",
            "USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION"
        ]:
            # L'acteur lui-même (s'il est un admin) est notifié de ses propres actions importantes
            if actor and actor.is_active:
                dest_user_ids.add(actor.pk)
            
            # Si la cible est un ADMIN_TECH/ADMIN_ZONE/WS_USER, il doit être notifié
            if target_user and target_user.is_active and action not in ["USER_DELETED"]:
                if target_user.role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
                    dest_user_ids.add(target_user.pk)
            
            # Les Admin Techs/Admin Zones sont notifiés des impersonations (hors leur propre impersonation)
            if action in ["USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION"]:
                # Notifier les ADMIN_TECHs et ADMIN_ZONEs (sauf s'ils sont l'acteur ou la cible)
                all_admin_pks = set(CustomUser.objects.filter(Q(role='ADMIN_TECH') | Q(role='ADMIN_ZONE'), is_active=True).values_list('pk', flat=True))
                if actor: all_admin_pks.discard(actor.pk)
                if target_user: all_admin_pks.discard(target_user.pk)
                if impersonator: all_admin_pks.discard(impersonator.pk) # Notifier l'impersonateur s'il revient
                dest_user_ids.update(all_admin_pks)

    else: # Pour les logs de niveau 'info' qui ne sont pas dans la liste des actions spécifiques ci-dessus (ex: API_ACCESS_...)
        # Ou les logs 'FAILED' qui ont déjà affiché une erreur UI
        return # Pas de notification UI pour ces actions, l'erreur est déjà visible UI ou c'est un log de détail non-critique.


    # Créer les notifications pour chaque destinataire unique
    for dest_user_id in dest_user_ids:
        create_ui_notification(
            user_id=dest_user_id,
            message=details, # Utilise le message 'details' déjà enrichi
            level=level,
            related_log_entry_id=log_entry.pk
        )

def create_ui_notification(user_id, message, level='info', related_log_entry_id=None):
    """
    Crée une notification pour être affichée dans l'interface utilisateur.
    """
    try:
        user = CustomUser.objects.get(pk=user_id)
        related_log = None
        if related_log_entry_id:
            try:
                related_log = LogEntry.objects.get(pk=related_log_entry_id)
            except LogEntry.DoesNotExist:
                print(f"Warning: Related LogEntry with ID {related_log_entry_id} not found for UI notification.", file=sys.stderr)

        UINotification.objects.create(
            user=user, 
            message=message, 
            level=level,
            related_log_entry=related_log 
        )
    except CustomUser.DoesNotExist:
        print(f"Warning: Could not create UI notification for non-existent user with ID {user_id}. Message: {message}", file=sys.stderr)
    except Exception as e:
        print(f"Error creating UI notification for user {user_id}: {e}", file=sys.stderr)