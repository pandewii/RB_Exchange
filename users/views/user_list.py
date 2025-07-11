from rest_framework.views import APIView
from rest_framework.response import Response

from users.models import CustomUser
from users.serializers.user_list import UserListSerializer
from ..permissions import IsSuperAdminOnly

class SuperAdminUserListView(APIView):
    permission_classes = [IsSuperAdminOnly]

    def get(self, request):
        users = CustomUser.objects.all().order_by("id")
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data)
