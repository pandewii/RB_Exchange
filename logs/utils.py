# logs/utils.py

from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.db.models import Q # Pour des requêtes plus complexes
import sys
from datetime import datetime

def log_action(actor_id, action, details, impersonator_id=None, source_id=None, target_user_id=None, level='info', currency_code=None, zone_id=None):
    """
    Enregistre une action dans le système de logs et génère des notifications UI ciblées.
    """
    actor = None
    if actor_id:
        try:
            actor = CustomUser.objects.get(pk=actor_id)
        except CustomUser.DoesNotExist:
            print(f"Warning: Actor with ID {actor_id} not found for log_action.", file=sys.stderr)
            pass 

    impersonator = None
    if impersonator_id:
        try:
            impersonator = CustomUser.objects.get(pk=impersonator_id)
            # Log l'impersonation elle-même (action par l'impersonator)
            # Ce log est séparé pour éviter les boucles si log_action est appelé pendant l'impersonation.
            LogEntry.objects.create(
                actor=impersonator,
                action="IMPERSONATION_STARTED",
                details=f"Impersonation started for user {actor.email} (ID: {actor.pk}) by {impersonator.email} (ID: {impersonator.pk}).",
                target_user=actor,
                level='info'
            )
        except CustomUser.DoesNotExist:
            print(f"Warning: Impersonator with ID {impersonator_id} not found for log_action.", file=sys.stderr)
            pass 

    target_user = None
    if target_user_id:
        try:
            target_user = CustomUser.objects.get(pk=target_user_id)
        except CustomUser.DoesNotExist:
            print(f"Warning: Target user with ID {target_user_id} not found for log_action.", file=sys.stderr)
            pass

    # Créer l'entrée de log principale
    log_entry = LogEntry.objects.create(
        actor=actor,
        impersonator=impersonator,
        target_user=target_user,
        action=action,
        details=details,
        level=level,
        # Les champs source_id, zone_id, currency_code ne sont pas directement des colonnes du modèle LogEntry.
        # Ils sont utilisés ici pour le ciblage des notifications et pour enrichir 'details'.
    )

    # --- LOGIQUE DE NOTIFICATION UI AFFINÉE ---
    
    # Seuls les logs de niveau 'warning', 'error', 'critical' sont des candidats pour les notifications UI
    if level not in ['warning', 'error', 'critical']:
        return # Pas de notification UI pour les logs info ou autres niveaux non définis

    dest_user_ids = set() # Utiliser un set pour éviter les doublons (ID utilisateur)

    # Pré-charger les PKs des SuperAdmins et Admin Techs actifs pour des recherches rapides
    superadmins_active_pks = set(CustomUser.objects.filter(role='SUPERADMIN', is_active=True).values_list('pk', flat=True))
    admin_techs_active_pks = set(CustomUser.objects.filter(role='ADMIN_TECH', is_active=True).values_list('pk', flat=True))
    
    # 1. Notifications pour les problèmes d'Accès & Sécurité
    if action in [
        "UNAUTHORIZED_ACCESS_ATTEMPT",
        "UNAUTHORIZED_DASHBOARD_ACCESS",
        "USER_LOGIN_FAILED_API", # Échec de connexion via API (seul cas API notifié)
        "USER_NOT_FOUND" # Utilisateur non trouvé pour un accès au dashboard
    ]:
        # Qui est alerté ? Le SuperAdmin (c'est une question de sécurité générale)
        dest_user_ids.update(superadmins_active_pks)

    # 2. Notifications pour la gestion des Zones & Sources (par Admin Technique ou liés au système)
    # C'est ici que le SuperAdmin doit voir les "grandes lignes" de l'Admin Tech.
    elif action in [
        "ZONE_DELETION_FAILED",  # Échec de suppression de zone (ex: associée à des utilisateurs)
        "ZONE_DELETED",         # Succès de suppression de zone
        "ZONE_STATUS_TOGGLED",  # Activation/Désactivation de zone
        "SCRAPER_SCRIPT_NOT_FOUND", # Problèmes avec les scripts (pas de chemin relatif ici)
        "SCRAPER_DIR_NOT_FOUND",    # Problème de répertoire des scrapers
        "SCRAPER_LISTING_FAILED",   # Problème pour lister les scrapers
        "SCHEDULE_MANAGEMENT_FAILED" # Échec de gestion de planification
    ]:
        # Qui est alerté ? SuperAdmin et tous les Admin Techniques actifs (car ce sont les gestionnaires)
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        # Et l'acteur lui-même (s'il est un Admin Tech) s'il n'est pas déjà inclus.
        if actor and actor.is_active and actor.pk in admin_techs_active_pks:
            dest_user_ids.add(actor.pk)

    # 3. Notifications pour l'Exécution des Scrapers & Pipeline (Automatisé)
    # Ces erreurs critiques doivent alerter les Admin Techniques et SuperAdmins.
    elif action in [
        "SCRAPER_TIMEOUT",
        "SCRAPER_EXECUTION_ERROR",
        "SCRAPER_INVALID_JSON",
        "SCRAPER_UNEXPECTED_ERROR",
        "RAW_DATA_DATE_PARSE_ERROR",
        "RAW_DATA_VALUE_PARSE_ERROR",
        "PIPELINE_CALCULATION_ERROR",
        "PIPELINE_ERROR",
        "PIPELINE_UNEXPECTED_ERROR_START"
    ]:
        # Qui est alerté ? Admin Techniques et SuperAdmins
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        # Si l'erreur est liée à une zone spécifique, s'assurer que l'Admin Tech de cette zone est bien notifié.
        if zone_id:
            # On cherche les Admin Techs spécifiquement liés à cette zone
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone) # Ajoute les AT de la zone spécifique

    # 4. Notifications pour la Gestion des Devises Activées (par Admin Zone)
    elif action == "CURRENCY_ACTIVATION_TOGGLED":
        # Qui est alerté ? SuperAdmins, Admin Techs (car ils gèrent les zones), et l'Admin Zone qui a initié l'action
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks) # Ajouté pour que les ATs voient les toggles de devises
        
        if actor and actor.is_active and actor.role == 'ADMIN_ZONE':
            dest_user_ids.add(actor.pk) # L'Admin Zone est notifié de sa propre action importante

    # Cas des actions qui ne génèrent PAS de notification UI (selon votre spécification)
    elif action in [
        # Exclusions de validation de formulaire UI (l'utilisateur voit l'erreur directement)
        "ADMIN_CREATION_FAILED", "CONSUMER_CREATION_FAILED", "USER_MODIFICATION_FAILED",
        "ZONE_CREATION_FAILED", # Échec de création de zone via UI
        "ZONE_PROPERTIES_UPDATE_FAILED", # Échec de mise à jour des propriétés de zone via UI
        "SOURCE_CONFIGURATION_FAILED", # Échec de configuration de source via UI
        "ALIAS_CREATION_FAILED", # Échec de création d'alias via UI
        # Exclusions d'actions SuperAdmin sur SuperAdmin (acteur déjà informé)
        "SUPERADMIN_MODIFICATION_ATTEMPT", "SUPERADMIN_DELETION_ATTEMPT_FAILED", "SUPERADMIN_STATUS_TOGGLE_ATTEMPT",
        # Exclusion spécifique demandée
        "CURRENCY_TOGGLE_FAILED_NO_ZONE"
    ]:
        return # Pas de notification UI pour ces actions.


    # Créer les notifications pour chaque destinataire unique
    for dest_user_id in dest_user_ids:
        create_ui_notification(
            user_id=dest_user_id,
            message=details,
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