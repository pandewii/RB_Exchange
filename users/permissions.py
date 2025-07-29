# users/permissions.py

from rest_framework.permissions import BasePermission
from users.models import CustomUser

class IsSuperAdminOnly(BasePermission):
    """
    Custom permission to allow only SuperAdmins to access.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "SUPERADMIN"


class IsAdminTechniqueOnly(BasePermission):
    """
    Custom permission to allow only AdminTechnique users to access.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN_TECH"

class IsWebServiceUserOnly(BasePermission):
    """
    Custom permission to allow only WebServiceUser to access API endpoints.
    """
    def has_permission(self, request, view):
        # Allow access only if the user is authenticated and has the WS_USER role
        return request.user.is_authenticated and request.user.role == "WS_USER"

