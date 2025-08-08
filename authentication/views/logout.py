from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema  # Ajouté pour Swagger
from authentication.serializers import LogoutSerializer
from django.shortcuts import redirect
from logs.utils import log_action
from users.models import CustomUser

@extend_schema(
    request=LogoutSerializer,
    responses={
        205: None,
        400: None,
        500: None
    }
)
class APILogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refresh_token_value = serializer.validated_data.get("refresh")
        user_for_log = request.user if request.user.is_authenticated else None

        try:
            token = RefreshToken(refresh_token_value)
            token_jti = token['jti']
            token_user_id = token['user_id']
            token.blacklist()

            final_user_obj_for_log = user_for_log or CustomUser.objects.filter(pk=token_user_id).first()

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
            log_action(
                actor_id=user_for_log.pk if user_for_log else None,
                action='API_LOGOUT_FAILED',
                details=f"Échec déconnexion API pour {user_for_log.email if user_for_log else 'Inconnu'}. Erreur: {e}. Token: '{refresh_token_value[:10]}...'",
                level='warning',
                zone_obj=user_for_log.zone if user_for_log and user_for_log.zone else None,
                source_obj=None
            )
            return Response({"error": f"Token invalide ou déjà blacklisté: {e}."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            log_action(
                actor_id=user_for_log.pk if user_for_log else None,
                action='API_LOGOUT_FAILED',
                details=f"Erreur inattendue lors de la déconnexion API pour {user_for_log.email if user_for_log else 'Inconnu'}. Erreur: {e}.",
                level='critical',
                zone_obj=user_for_log.zone if user_for_log and user_for_log.zone else None,
                source_obj=None
            )
            return Response({"error": "Une erreur inattendue est survenue."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
