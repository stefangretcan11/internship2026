from rest_framework.permissions import BasePermission


class IsActiveUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.status == 'active'
        )


class IsCitizen(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'citizen'
        )


class IsValidator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'validator'
        )


class IsAgent(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'agent'
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role == 'admin'
        )


class IsAgentOrAbove(BasePermission):
    ALLOWED_ROLES = {'agent', 'validator', 'admin', 'superadmin'}

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.status == 'active'
            and request.user.role in self.ALLOWED_ROLES
        )


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == 'superadmin'
        )
