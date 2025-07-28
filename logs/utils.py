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

    # Créer l'entrée de log principale
    log_entry = LogEntry.objects.create(
        actor=actor,
        impersonator=impersonator,
        target_user=target_user,
        action=action,
        details=details, # Utilise le message 'details' déjà enrichi
        level=level,
    )

    # --- LOGIQUE DE NOTIFICATION UI AFFINÉE ---
    
    # Seuls les logs de niveau 'warning', 'error', 'critical' sont des candidats pour les notifications UI
    if level not in ['warning', 'error', 'critical', 'info']: # Inclure 'info' si certaines notifications info sont désirées
        return # Pas de notification UI pour les logs info ou autres niveaux non définis

    dest_user_ids = set() # Utiliser un set pour éviter les doublons (ID utilisateur)

    # Pré-charger les PKs des SuperAdmins et Admin Techs actifs pour des recherches rapides
    superadmins_active_pks = set(CustomUser.objects.filter(role='SUPERADMIN', is_active=True).values_list('pk', flat=True))
    admin_techs_active_pks = set(CustomUser.objects.filter(role='ADMIN_TECH', is_active=True).values_list('pk', flat=True))
    
    # 1. Notifications pour les problèmes d'Accès & Sécurité
    if action in [
        "UNAUTHORIZED_ACCESS_ATTEMPT",
        "UNAUTHORIZED_DASHBOARD_ACCESS",
        "USER_LOGIN_FAILED_API",
        "USER_NOT_FOUND"
    ]:
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks) # Admin Techs sont aussi concernés par la sécurité système

    # 2. Notifications pour la gestion des Zones & Sources & Planifications & Alias
    # Ces actions concernent les SuperAdmins et les Admin Techs (gardien de l'infrastructure)
    elif action in [
        "ZONE_DELETION_FAILED", "ZONE_DELETED", "ZONE_STATUS_TOGGLED", "ZONE_CREATED", "ZONE_PROPERTIES_UPDATED",
        "SOURCE_CONFIGURED", "SOURCE_MODIFIED", "SOURCE_DELETED", "SOURCE_CONFIGURATION_FAILED",
        "SCRAPER_SCRIPT_NOT_FOUND", "SCRAPER_DIR_NOT_FOUND", "SCRAPER_LISTING_FAILED",
        "SCHEDULE_MANAGEMENT_FAILED", "SCHEDULE_CREATED", "SCHEDULE_MODIFIED", "SCHEDULE_DELETED",
        "ALIAS_CREATED", "ALIAS_MODIFIED", "ALIAS_DELETED", "ALIAS_MANAGEMENT_FAILED",
    ]:
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        # Si l'action a un contexte de zone, notifier les AdminTechs spécifiques à cette zone
        if zone_id:
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone)

    # 3. Notifications pour l'Exécution des Scrapers & Pipeline (Automatisé)
    # Erreurs critiques pour les SuperAdmins et Admin Techs
    elif action in [
        "SCRAPER_TIMEOUT", "SCRAPER_EXECUTION_ERROR", "SCRAPER_INVALID_JSON", "SCRAPER_UNEXPECTED_ERROR",
        "RAW_DATA_DATE_PARSE_ERROR", "RAW_DATA_VALUE_PARSE_ERROR", "PIPELINE_CALCULATION_ERROR",
        "PIPELINE_ERROR", "PIPELINE_UNEXPECTED_ERROR_START"
    ]:
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        if zone_id: # Pour cibler les Admin Techs d'une zone spécifique en cas d'erreur scraper/pipeline
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone)

    # 4. Notifications pour la Gestion des Devises Activées (par Admin Zone)
    # C'est la responsabilité de l'Admin Zone, donc il est le destinataire principal avec les SuperAdmins
    elif action == "CURRENCY_ACTIVATION_TOGGLED":
        dest_user_ids.update(superadmins_active_pks) # SuperAdmins toujours informés
        
        # Admin Zones de la zone concernée
        if zone_id:
            admin_zones_in_zone = CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_zones_in_zone)
        # ADMIN_TECHs NE SONT PLUS NOTIFIÉS PAR DÉFAUT POUR CETTE ACTION.
        # Si un AdminTech doit être notifié, cela doit être via son rôle d'AdminZone de la même zone.

    # 5. Notifications pour les actions utilisateur (création/modification/suppression/statut/impersonation)
    elif action in [
        "ADMIN_CREATED", "CONSUMER_CREATED", "USER_MODIFIED", "USER_DELETED", "USER_STATUS_TOGGLED",
        "SUPERADMIN_MODIFICATION_ATTEMPT", "SUPERADMIN_DELETION_FAILED", "SUPERADMIN_STATUS_TOGGLE_ATTEMPT",
        "USER_IMPERSONATED", "USER_REVERTED_IMPERSONATION"
    ]:
        dest_user_ids.update(superadmins_active_pks) # SuperAdmins toujours notifiés des actions sur les utilisateurs
        
        # L'acteur lui-même est notifié de ses propres actions importantes
        if actor and actor.is_active:
            dest_user_ids.add(actor.pk)
        
        # Si un ADMIN_TECH agit sur un utilisateur, il est notifié.
        # Si la cible est un ADMIN_TECH/ADMIN_ZONE, il doit être notifié par le SuperAdmin
        if target_user and target_user.is_active and action not in ["USER_DELETED"]:
             if target_user.role == 'ADMIN_TECH' :
                 dest_user_ids.add(target_user.pk)
             if target_user.role == 'ADMIN_ZONE':
                 dest_user_ids.add(target_user.pk)


    # Cas des actions qui ne génèrent PAS de notification UI (selon votre spécification)
    elif action in [
        "ADMIN_CREATION_FAILED", "CONSUMER_CREATION_FAILED", "USER_MODIFICATION_FAILED",
        "CURRENCY_TOGGLE_FAILED_NO_ZONE", "ZONE_PROPERTIES_UPDATE_FAILED", "ZONE_CREATION_FAILED"
    ]:
        return # Pas de notification UI pour ces actions, l'erreur est déjà visible UI.


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