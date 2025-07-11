from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from users.serializers.admin_create import AdminCreateSerializer
from users.models import CustomUser
from ..permissions import IsSuperAdminOnly

class SuperAdminCreateAdminView(APIView):
    permission_classes = [IsSuperAdminOnly]

    def post(self, request):
        # 🔒 Vérifie que l'utilisateur est un SuperAdmin
        if request.user.role != 'SUPERADMIN':
            return Response({'detail': "Accès refusé."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AdminCreateSerializer(data=request.data)
        if serializer.is_valid():
            
            user = serializer.save()
            return Response({
                "message": f"Administrateur {user.email} créé avec succès.",
                "user" : {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "zone": user.zone.nom if user.zone else None
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
