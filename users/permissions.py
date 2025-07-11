from rest_framework.permissions import BasePermission

class IsSuperAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "SUPERADMIN"


class IsAdminTechniqueOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN_TECH"

