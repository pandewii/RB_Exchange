# authentication/views/impersonate.py

from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.views import View
from users.models import CustomUser
from logs.utils import log_action 
from django.conf import settings 

class ImpersonateView(View):
    # ... (ImpersonateView content remains unchanged)
    def post(self, request, user_id):
        # Ensure the requesting user is authenticated
        if not request.user.is_authenticated:
            return redirect('login')

        original_user = request.user # The user currently authenticated (could be real or already impersonated)
        target_user = get_object_or_404(CustomUser, pk=user_id)

        # Basic access control checks
        if original_user == target_user:
            response = HttpResponse(status=403)
            response['HX-Trigger'] = '{"showError": "Action non autorisée : Impossible d\'impersonner soi-même."}'
            return response

        if target_user.role == 'SUPERADMIN':
            response = HttpResponse(status=403)
            response['HX-Trigger'] = '{"showError": "Action non autorisée : Impossible d\'impersonner un SuperAdmin."}'
            return response

        # Check hierarchical impersonation rules
        can_impersonate = False
        if original_user.role == 'SUPERADMIN' and target_user.role in ['ADMIN_TECH', 'ADMIN_ZONE', 'WS_USER']:
            can_impersonate = True
        elif original_user.role == 'ADMIN_TECH' and target_user.role == 'ADMIN_ZONE':
            can_impersonate = True

        if not can_impersonate:
            response = HttpResponse(status=403)
            response['HX-Trigger'] = '{"showError": "Accès non autorisé : Vous n\'avez pas la permission d\'impersonner cet utilisateur."}'
            return response

        # --- Impersonation Stack Logic ---
        # Initialize stack if it doesn't exist
        if 'impersonation_stack' not in request.session:
            request.session['impersonation_stack'] = []

        # Save current user's state to the stack (this is the user who is *about to be impersonated*)
        request.session['impersonation_stack'].append({
            'user_id': original_user.pk,
            'role': original_user.role,
            'email': original_user.email,
            'auth_user_id': request.session.get('_auth_user_id'), # Store Django's internal auth ID
            'auth_user_backend': request.session.get('_auth_user_backend'), # Store Django's internal auth backend
        })
        
        # Store the target user's ID in a temporary session variable
        request.session['impersonate_target_user_id'] = target_user.pk
        
        # Log the impersonation action
        # Determine the root actor for logging (the very first user in the chain)
        root_actor_id = request.session['impersonation_stack'][0]['user_id'] # This should always exist when pushing
        root_actor = get_object_or_404(CustomUser, pk=root_actor_id)

        log_details = (
            f"L'utilisateur {root_actor.email} (ID: {root_actor.pk}, Rôle: {root_actor.get_role_display()}) "
            f"a commencé à impersonner {target_user.email} (ID: {target_user.pk}, Rôle: {target_user.get_role_display()})."
        )
        if original_user.pk != root_actor.pk: # If this is a nested impersonation
            log_details += f" Cela a été fait depuis l'impersonation de {original_user.email} (ID: {original_user.pk}, Rôle: {original_user.get_role_display()})."

        log_action(
            actor_id=root_actor.pk,
            impersonator_id=original_user.pk, # The user from whom the impersonation originated (previous in chain)
            target_user_id=target_user.pk, # The user being impersonated
            action='USER_IMPERSONATED',
            details=log_details,
            level='info',
        )

        # Redirect to the helper view which will perform the actual login and then redirect to dashboard
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('impersonate_login_helper') # Redirect to the helper view
        response['HX-Trigger'] = f'{{"showInfo": "Impersonation de {target_user.email} en tant que {target_user.get_role_display()}."}}'
        return response


class RevertImpersonationView(View):
    """
    Permet à un utilisateur impersonné de revenir à son rôle original ou au niveau précédent de la pile.
    """
    def post(self, request):
        # Ensure the requesting user is authenticated
        if not request.user.is_authenticated:
            return redirect('login')

        # Check if 'impersonation_stack' exists and is not empty
        if 'impersonation_stack' not in request.session or not request.session['impersonation_stack']:
            response = HttpResponse(status=400)
            response['HX-Trigger'] = '{"showError": "Aucune session d\'impersonation active à revenir."}'
            return response
        
        # The user we are currently impersonating (before reverting)
        current_impersonated_user_obj = request.user 

        # Pop the last state from the stack
        previous_state = request.session['impersonation_stack'].pop()
        
        # Store the ID of the user to be restored in a temporary session variable
        request.session['impersonate_target_user_id'] = previous_state['user_id'] # Use the previous_state's user_id as target
        
        # Log the reversion action BEFORE actual login helper redirect
        # Fetch the user object that will be active after reverting
        restored_user = get_object_or_404(CustomUser, pk=previous_state['user_id'])
        
        # Determine the root actor for logging
        if not request.session.get('impersonation_stack'):
            root_actor = restored_user
        else:
            root_actor_id = request.session['impersonation_stack'][0]['user_id']
            root_actor = get_object_or_404(CustomUser, pk=root_actor_id)


        log_details = (
            f"L'utilisateur {root_actor.email} (ID: {root_actor.pk}, Rôle: {root_actor.get_role_display()}) "
            f"est revenu de l'impersonation de {current_impersonated_user_obj.email} (ID: {current_impersonated_user_obj.pk}, Rôle: {current_impersonated_user_obj.get_role_display()}) "
            f"à {restored_user.email} (ID: {restored_user.pk}, Rôle: {restored_user.get_role_display()})."
        )

        log_action(
            actor_id=root_actor.pk, 
            impersonator_id=current_impersonated_user_obj.pk, # The user from whom we reverted
            target_user_id=restored_user.pk, # The user to whom we reverted
            action='USER_REVERTED_IMPERSONATION',
            details=log_details,
            level='info',
        )
        
        # Redirect to the helper view which will perform the actual login and then redirect to dashboard
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('impersonate_login_helper') # Redirect to the helper view
        response['HX-Trigger'] = f'{{"showSuccess": "Vous êtes revenu à votre rôle ({restored_user.get_role_display()})." }}'
        return response