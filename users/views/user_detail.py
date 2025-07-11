from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.models import CustomUser
from users.serializers.admin_update import AdminUpdateSerializer
from ..permissions import IsSuperAdminOnly

class SuperAdminUserDetailView(APIView):
    permission_classes = [IsSuperAdminOnly]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"message": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if user.role == "SUPERADMIN":
            return Response({"message": "Impossible de modifier un SuperAdmin."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AdminUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response({
                "message": "Utilisateur modifié avec succès.",
                "user": {
                    "id": updated_user.id,
                    "email": updated_user.email,
                    "role": updated_user.role,
                    "zone": updated_user.zone.nom if updated_user.zone else None
                }
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"message": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if user.role == "SUPERADMIN":
            return Response({"message": "Impossible de supprimer un SuperAdmin."}, status=status.HTTP_403_FORBIDDEN)

        email = user.email
        user.delete()
        return Response({"message": f"Utilisateur {email} supprimé avec succès."}, status=status.HTTP_200_OK)
