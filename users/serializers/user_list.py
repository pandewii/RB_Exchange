from rest_framework import serializers
from users.models import CustomUser

class UserListSerializer(serializers.ModelSerializer):
    zone = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'role', 'is_active', 'zone']

    def get_zone(self, obj):
        return obj.zone.nom if obj.zone else None
