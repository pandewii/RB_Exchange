
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from core.models.zone_monetaire import ZoneMonetaire
from core.serializers.zone_monetaire import ZoneMonetaireSerializer
from users.permissions import  IsAdminTechniqueOnly

@api_view(['POST'])
@permission_classes([IsAdminTechniqueOnly])
def create_zone(request):
    serializer = ZoneMonetaireSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAdminTechniqueOnly])
def list_zones(request):
    zones = ZoneMonetaire.objects.all()
    serializer = ZoneMonetaireSerializer(zones, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
