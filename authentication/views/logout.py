from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.shortcuts import redirect 
# REMOVED: from django.views import View as DjangoView # No longer needed here if only APILogoutView
from logs.utils import log_action 
from users.models import CustomUser 
# REMOVED: from django.contrib.auth import logout as auth_logout 
# REMOVED: from django.http import HttpResponseRedirect 
# REMOVED: from django.conf import settings 


# This class handles API logout (expects refresh token in POST data)
class APILogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token_value = request.data.get("refresh")
        
        user_for_log = None
        if request.user.is_authenticated:
            user_for_log = request.user
        
        if not refresh_token_value:
            log_action(
                actor_id=user_for_log.pk if user_for_log else None,
                action='API_LOGOUT_FAILED',
                details=f"Échec déconnexion API: champ 'refresh' manquant. Utilisateur: {user_for_log.email if user_for_log else 'Inconnu'}.",
                level='warning',
                zone_obj=user_for_log.zone if user_for_log and user_for_log.zone else None,
                source_obj=None
            )
            return Response({"error": "Le champ 'refresh' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token_value)
            token_jti = token['jti'] 
            token_user_id = token['user_id'] 

            token.blacklist()

            final_user_obj_for_log = user_for_log 
            if not final_user_obj_for_log: 
                final_user_obj_for_log = CustomUser.objects.filter(pk=token_user_id).first()
            
            log_action(
                actor_id=final_user_obj_for_log.pk if final_user_obj_for_log else None,
                action='API_LOGOUT_SUCCESS',
                details=f"Déconnexion API réussie pour l'utilisateur {final_user_obj_for_log.email if final_user_obj_for_log else 'ID ' + str(token_user_id)}. Refresh token blacklisté (JTI: {token_jti}).", 
                level='info',
                zone_obj=final_user_obj_for_log.zone if final_user_obj_for_log and final_user_obj_for_log.zone else None,
                source_obj=None
            )
            return Response({"message": "Déconnexion réussie."}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            user_info = user_for_log.email if user_for_log else "Inconnu"
            log_action(
                actor_id=user_for_log.pk if user_for_log else None,
                action='API_LOGOUT_FAILED',
                details=f"Échec déconnexion API pour {user_info}. Erreur: {e}. Token: '{refresh_token_value[:10]}...'",
                level='warning',
                zone_obj=user_for_log.zone if user_for_log and user_for_log.zone else None,
                source_obj=None
            )
            return Response({"error": f"Token invalide ou déjà blacklisté: {e}."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            user_info = user_for_log.email if user_for_log else "Inconnu"
            log_action(
                actor_id=user_for_log.pk if user_for_log else None,
                action='API_LOGOUT_FAILED',
                details=f"Erreur inattendue lors de la déconnexion API pour {user_info}. Erreur: {e}.",
                level='critical',
                zone_obj=user_for_log.zone if user_for_log and user_for_log.zone else None,
                source_obj=None
            )
            return Response({"error": "Une erreur inattendue est survenue."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)