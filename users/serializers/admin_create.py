from rest_framework import serializers
from users.models import CustomUser
from core.models import ZoneMonetaire  # à créer plus tard si pas encore fait

class AdminCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    zone_id = serializers.IntegerField(required=False)

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'role', 'zone_id']

    def validate(self, attrs):
        role = attrs.get('role')
        zone_id = attrs.get('zone_id')

        if role == 'ADMIN_ZONE' and not zone_id:
            raise serializers.ValidationError("Le champ 'zone_id' est obligatoire pour un AdminZone.")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        zone_id = validated_data.pop('zone_id', None)

        user = CustomUser(**validated_data)
        user.set_password(password)

        if validated_data['role'] == 'ADMIN_ZONE' and zone_id:
            user.zone_id = zone_id  # type: ignore

        user.save()
        return user
