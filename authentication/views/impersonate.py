# authentication/views/impersonate.py

from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.views import View
from users.models import CustomUser
from logs.utils import log_action 
from django.conf import settings 

class ImpersonateView(View):
    def post(self, request, user_id):
        if not request.session.get('user_id'):
            return redirect('login')

        current_user_pk = request.session['user_id']
        original_user = get_object_or_404(CustomUser, pk=current_user_pk) # L'utilisateur actuellement connecté/impersonné
        target_user = get_object_or_404(CustomUser, pk=user_id)

        # Empêcher l'impersonation de soi-même ou d'un SuperAdmin
        if original_user == target_user or target_user.role == 'SUPERADMIN':
            response = HttpResponse(status=403)
            response['HX-Trigger'] = '{"showError": "Action non autorisée : Impossible d\'impersonner un SuperAdmin ou soi-même."}'
            return response

        # Vérifier les règles d'impersonation descendantes
        can_impersonate = False
        if original_user.role == 'SUPERADMIN' and target_user.role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            can_impersonate = True
        elif original_user.role == 'ADMIN_TECH' and target_user.role == 'ADMIN_ZONE':
            can_impersonate = True

        if not can_impersonate:
            response = HttpResponse(status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé : Vous n\'avez pas la permission d\'impersonner cet utilisateur."}'
            return response

        # --- DÉBUT DE LA LOGIQUE DE PILE (STACK) POUR L'IMPERSONATION ---
        
        # Initialiser la pile si elle n'existe pas
        if 'impersonation_stack' not in request.session:
            request.session['impersonation_stack'] = []

        # Pousser l'état actuel de la session sur la pile
        # Nous stockons le user_id, le role et l'email de l'utilisateur AVANT l'impersonation
        request.session['impersonation_stack'].append({
            'user_id': request.session['user_id'],
            'role': request.session['role'],
            'email': request.session['email'],
        })

        # --- FIN DE LA LOGIQUE DE PILE ---
        
        # Mettre à jour la session avec les informations de l'utilisateur impersonné
        request.session['user_id'] = target_user.pk
        request.session['role'] = target_user.role
        request.session['email'] = target_user.email
        
        # Enregistrer l'action dans les logs
        # L'acteur est toujours l'utilisateur ORIGINAL (le vrai SuperAdmin/AdminTech qui a initié la chaîne)
        # L'impersonateur est l'utilisateur ACTUEL au moment de l'impersonation
        # Le target_user est celui que l'on commence à impersonner MAINTENANT
        
        # Récupérer l'utilisateur le plus original de la chaîne pour le log si la pile n'est pas vide
        # ou l'original_user si c'est la première impersonation.
        root_actor_id = request.session['impersonation_stack'][0]['user_id'] if request.session['impersonation_stack'] else original_user.pk
        root_actor = get_object_or_404(CustomUser, pk=root_actor_id)

        log_action(
            actor_id=root_actor.pk,  # Le SuperAdmin/AdminTech à la racine de la chaîne
            impersonator_id=original_user.pk, # L'utilisateur d'où l'on vient (celui qu'on était juste avant)
            target_user_id=target_user.pk, # L'utilisateur qu'on commence à impersonner
            action='USER_IMPERSONATED',
            details=f"L'utilisateur {root_actor.email} a impersonné {target_user.email} ({target_user.get_role_display()}) via {original_user.email}.",
            level='info',
        )

        # Rediriger vers le tableau de bord de l'utilisateur impersonné
        dashboard_url = ''
        if target_user.role == 'ADMIN_TECH':
            dashboard_url = reverse('admin_technique_dashboard')
        elif target_user.role == 'ADMIN_ZONE':
            dashboard_url = reverse('admin_zone_dashboard')
        elif target_user.role == 'WS_USER':
            dashboard_url = reverse('index') 
            response = HttpResponse(status=204) 
            response['HX-Trigger'] = '{"showInfo": "Vous impersonnez un utilisateur WebService. Il n\'y a pas de tableau de bord dédié."}'
            response['HX-Redirect'] = dashboard_url
            return response
        else: # Cas inattendu ou SuperAdmin (qui est bloqué)
             dashboard_url = reverse('index') # Fallback sûr

        response = HttpResponse(status=204) 
        response['HX-Redirect'] = dashboard_url
        response['HX-Trigger'] = f'{{"showInfo": "Impersonation de {target_user.email} en tant que {target_user.get_role_display()}."}}'
        return response


class RevertImpersonationView(View):
    """
    Permet à un utilisateur impersonné de revenir à son rôle original ou au niveau précédent de la pile.
    """
    def post(self, request):
        if 'impersonation_stack' not in request.session or not request.session['impersonation_stack']:
            response = HttpResponse(status=400)
            response['HX-Trigger'] = '{"showError": "Aucune session d\'impersonation active à revenir."}'
            return response
        
        # L'utilisateur que nous étions juste avant de cliquer sur Revert
        current_impersonated_user_pk = request.session['user_id']
        current_impersonated_user = get_object_or_404(CustomUser, pk=current_impersonated_user_pk)

        # Pop le dernier état de la pile
        previous_state = request.session['impersonation_stack'].pop()
        
        # Restaurer la session avec l'état précédent
        request.session['user_id'] = previous_state['user_id']
        request.session['role'] = previous_state['role']
        request.session['email'] = previous_state['email']

        # Récupérer l'utilisateur qui redevient actif
        restored_user = get_object_or_404(CustomUser, pk=previous_state['user_id'])
        
        # Pour le log: l'acteur est le "root" actor (premier de la pile si elle n'est pas vide, sinon l'utilisateur restauré)
        # l'impersonator est celui qu'on était juste avant de revenir.
        root_actor_id = request.session['impersonation_stack'][0]['user_id'] if request.session['impersonation_stack'] else restored_user.pk
        root_actor = get_object_or_404(CustomUser, pk=root_actor_id)


        log_action(
            actor_id=root_actor.pk, 
            impersonator_id=current_impersonated_user.pk, # L'utilisateur qu'on a quitté
            target_user_id=restored_user.pk, # L'utilisateur vers qui on est revenu
            action='USER_REVERTED_IMPERSONATION',
            details=f"L'utilisateur {root_actor.email} est revenu de l'impersonation de {current_impersonated_user.email} à {restored_user.email} ({restored_user.get_role_display()}).",
            level='info',
        )
        
        # Rediriger vers le tableau de bord de l'utilisateur original ou du niveau précédent
        dashboard_url = ''
        if restored_user.role == 'SUPERADMIN':
            dashboard_url = reverse('superadmin_dashboard')
        elif restored_user.role == 'ADMIN_TECH':
            dashboard_url = reverse('admin_technique_dashboard')
        elif restored_user.role == 'ADMIN_ZONE':
            dashboard_url = reverse('admin_zone_dashboard')
        elif restored_user.role == 'WS_USER': # Si on est revenu à un WS_USER (peu probable si les règles sont respectées)
            dashboard_url = reverse('index') # Fallback pour WS_USER

        response = HttpResponse(status=204) 
        response['HX-Redirect'] = dashboard_url
        response['HX-Trigger'] = f'{{"showSuccess": "Vous êtes revenu à votre rôle ({restored_user.get_role_display()})." }}'
        return response