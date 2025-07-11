from rest_framework import serializers
from users.models import CustomUser
from core.models import ZoneMonetaire

class AdminUpdateSerializer(serializers.ModelSerializer):
    zone_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'role', 'zone_id']

    def validate(self, attrs):
        # Retrieve role and zone_id, prioritizing new attrs over instance values for validation context
        role = attrs.get('role', self.instance.role if self.instance else None)
        # If instance exists and has a zone, get its ID, otherwise None
        zone_id = attrs.get('zone_id', self.instance.zone.id if self.instance and self.instance.zone else None)

        if role == 'ADMIN_ZONE' and not zone_id:
            raise serializers.ValidationError({"zone_id": "Le champ zone_id est requis pour le rôle ADMIN_ZONE."})

        # CORRECTION: Validate that the ZoneMonetaire exists if a zone_id is provided
        if zone_id is not None: # Use 'is not None' to correctly handle 0 if it were a valid ID
            try:
                # Store the ZoneMonetaire object directly in attrs to avoid another DB query in update()
                attrs['zone'] = ZoneMonetaire.objects.get(id=zone_id)
            except ZoneMonetaire.DoesNotExist:
                raise serializers.ValidationError({"zone_id": "La zone spécifiée n'existe pas."})
        else:
            # If zone_id is None, ensure 'zone' in attrs is also None.
            # This handles cases where a zone is explicitly unassigned or not required for the role.
            attrs['zone'] = None

        # If the role is ADMIN_TECH, ensure the zone is None, overriding any zone_id provided
        if role == 'ADMIN_TECH':
            attrs['zone'] = None # Force to None if AdminTech

        return attrs

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.role = validated_data.get('role', instance.role)

        # CORRECTION: Use the validated 'zone' object directly from validated_data
        # This 'zone' key was added in the validate method
        instance.zone = validated_data.get('zone', instance.zone) 

        instance.save()
        return instance