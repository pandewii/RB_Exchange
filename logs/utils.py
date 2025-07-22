# logs/utils.py

from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.db.models import Q
import sys
from datetime import datetime

def log_action(actor_id, action, details, impersonator_id=None, target_user_id=None, level='info', currency_code=None, zone_id=None):
    """
    Enregistre une action dans le système de logs et génère des notifications UI ciblées.
    Les messages 'details' sont maintenant supposés être construits de manière sémantique
    au point d'appel dans les vues.
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
            # La logique de double logging 'IMPERSONATION_STARTED' a été supprimée précédemment ici.
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
        "USER_LOGIN_FAILED_API",
        "USER_NOT_FOUND"
    ]:
        dest_user_ids.update(superadmins_active_pks)

    # 2. Notifications pour la gestion des Zones & Sources (par Admin Technique ou liés au système)
    elif action in [
        "ZONE_DELETION_FAILED",
        "ZONE_DELETED",
        "ZONE_STATUS_TOGGLED",
        "ZONE_CREATED", # AJOUTÉ : Notifier les admins des nouvelles zones
        "ZONE_PROPERTIES_UPDATED", # AJOUTÉ : Notifier les admins des modifications de zone
        "SCRAPER_SCRIPT_NOT_FOUND",
        "SCRAPER_DIR_NOT_FOUND",
        "SCRAPER_LISTING_FAILED",
        "SCHEDULE_MANAGEMENT_FAILED",
        "SCHEDULE_CREATED", # AJOUTÉ : Notifier les admins des nouvelles planifications
        "SCHEDULE_MODIFIED", # AJOUTÉ : Notifier les admins des planifications modifiées
        "SCHEDULE_DELETED", # AJOUTÉ : Notifier les admins des planifications supprimées
        "SOURCE_CONFIGURED", # AJOUTÉ : Notifier les admins des sources configurées
        "SOURCE_MODIFIED", # AJOUTÉ : Notifier les admins des sources modifiées
        "SOURCE_DELETED", # AJOUTÉ : Notifier les admins des sources supprimées
        "ALIAS_CREATED", # AJOUTÉ : Notifier les admins des alias créés
        "ALIAS_MODIFIED", # AJOUTÉ : Notifier les admins des alias modifiés
        "ALIAS_DELETED", # AJOUTÉ : Notifier les admins des alias supprimés
        "ALIAS_MANAGEMENT_FAILED", # AJOUTÉ : Notifier les admins des échecs de gestion d'alias

    ]:
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        # Et l'acteur lui-même (s'il est un Admin Tech) s'il n'est pas déjà inclus.
        if actor and actor.is_active and actor.pk in admin_techs_active_pks: # Vérifie que l'acteur est un AT actif
            dest_user_ids.add(actor.pk)
        
        # Si l'action est liée à une zone spécifique et que l'acteur est un SuperAdmin ou AdminTech,
        # on peut cibler les AdminTechs de cette zone (si applicable).
        # Cette partie nécessite que la vue appelante passe le zone_id si l'action est sur une zone.
        # Nous l'avions déjà prévu dans la signature de log_action.
        if zone_id:
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone) # Ajoute les AT de la zone spécifique


    # 3. Notifications pour l'Exécution des Scrapers & Pipeline (Automatisé)
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
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks)
        
        if zone_id: # Pour cibler les Admin Techs d'une zone spécifique en cas d'erreur scraper
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone)

    # 4. Notifications pour la Gestion des Devises Activées (par Admin Zone)
    elif action == "CURRENCY_ACTIVATION_TOGGLED":
        # Qui est alerté ? SuperAdmins, Admin Techs (car ils gèrent les zones), et l'Admin Zone qui a initié l'action
        dest_user_ids.update(superadmins_active_pks)
        dest_user_ids.update(admin_techs_active_pks) 
        
        # L'Admin Zone qui a fait l'action est notifié
        if actor and actor.is_active and actor.role == 'ADMIN_ZONE':
            dest_user_ids.add(actor.pk)

        # Si la devise activée/désactivée est dans un contexte de zone (ce qui est toujours le cas),
        # et s'il y a des Admin Techs liés à cette zone, ils devraient être notifiés.
        # Cela nécessite que currency_activation_toggled passe le zone_id.
        # (À vérifier lors de l'intégration de AdminZone si ce champ est passé)
        if zone_id:
            admin_techs_in_zone = CustomUser.objects.filter(role='ADMIN_TECH', zone__pk=zone_id, is_active=True).values_list('pk', flat=True)
            dest_user_ids.update(admin_techs_in_zone)
        
        # Et aussi les autres AdminZone de la même zone (si pertinent).
        # Cela nécessite d'avoir l'objet zone ou zone_id et de filtrer les autres AdminZone.
        if zone_id:
            other_admin_zones_in_zone = CustomUser.objects.filter(role='ADMIN_ZONE', zone__pk=zone_id, is_active=True).exclude(pk=actor_id).values_list('pk', flat=True)
            dest_user_ids.update(other_admin_zones_in_zone)


    # 5. Notifications pour les actions utilisateur (création/modification/suppression/statut)
    elif action in [
        "ADMIN_CREATED",
        "CONSUMER_CREATED",
        "USER_MODIFIED",
        "USER_DELETED",
        "USER_STATUS_TOGGLED",
        "SUPERADMIN_MODIFICATION_ATTEMPT", 
        "SUPERADMIN_DELETION_FAILED", 
        "SUPERADMIN_STATUS_TOGGLE_ATTEMPT",
        "USER_IMPERSONATED", # Notifier l'acteur original de l'impersonation lancée
        "USER_REVERTED_IMPERSONATION" # Notifier l'acteur original du retour d'impersonation
    ]:
        dest_user_ids.update(superadmins_active_pks) # SuperAdmins toujours notifiés des actions sur les utilisateurs
        
        # L'acteur lui-même est toujours notifié de ses propres actions importantes sur les utilisateurs
        if actor and actor.is_active:
            dest_user_ids.add(actor.pk)
        
        # Si l'action a une cible utilisateur (target_user), cette cible peut aussi être notifiée (si pertinent)
        if target_user and target_user.is_active and action not in ["USER_DELETED"]: # Ne pas notifier un user qui vient d'être supprimé
            # Exemple: un ADMIN_TECH pourrait être notifié s'il est désactivé par un SuperAdmin.
            # À décider si c'est souhaitable pour chaque cas.
            # Pour l'instant, on se concentre sur les rôles de gestion.
            pass


    # Cas des actions qui ne génèrent PAS de notification UI (selon votre spécification)
    elif action in [
        # Exclusions de validation de formulaire UI (l'utilisateur voit l'erreur directement)
        "ADMIN_CREATION_FAILED", "CONSUMER_CREATION_FAILED", "USER_MODIFICATION_FAILED",
        # Exclusion spécifique demandée
        "CURRENCY_TOGGLE_FAILED_NO_ZONE"
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