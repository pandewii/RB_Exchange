from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.models import CustomUser
from ..permissions import IsSuperAdminOnly

class SuperAdminToggleUserStatusView(APIView):
    permission_classes = [IsSuperAdminOnly]

    def patch(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
            if user.role == "SUPERADMIN":
                return Response(
                    {"error": "Impossible de modifier le statut d’un SuperAdmin."},
                    status=status.HTTP_403_FORBIDDEN
                )

            user.is_active = not user.is_active
            user.save()

            return Response({
                "message": f"Utilisateur {'activé' if user.is_active else 'désactivé'} avec succès.",
                "user": {
                    "id": user.id, # type: ignore
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "zone": user.zone.nom if user.zone else None
                }
            }, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé."}, status=status.HTTP_404_NOT_FOUND)
